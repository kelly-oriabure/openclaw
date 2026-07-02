#!/usr/bin/env python3
"""
Kie.ai Image Generation Module
Generates images using GROK text-to-image API and returns URLs.
"""

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Paths
VAULT_DIR = Path("/data/workspace/vault")

# Kie.ai API config
KIE_API_BASE = "https://api.kie.ai"
KIE_MODEL = "grok-imagine/text-to-image"

# Polling config
MAX_POLL_ATTEMPTS = 60  # Max attempts (60 * 5s = 5 minutes max)
POLL_INTERVAL = 5  # Seconds between polls


def get_api_key():
    """Decrypt Kie.ai API key from vault."""
    result = subprocess.run(
        ["age", "-d", "-i", str(VAULT_DIR / "age-key.txt"), "-o", "/dev/stdout",
         str(VAULT_DIR / "kie-api-key.age")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ Failed to decrypt API key: {result.stderr}")
        return None
    return result.stdout.strip()


def create_image_task(prompt, aspect_ratio="3:2", enable_pro=False):
    """
    Submit an image generation task to Kie.ai.
    
    Args:
        prompt: Text description of the desired image
        aspect_ratio: Image ratio (2:3, 3:2, 1:1, 16:9, 9:16)
        enable_pro: Use quality mode (True) or speed mode (False)
    
    Returns:
        Task ID if successful, None otherwise
    """
    api_key = get_api_key()
    if not api_key:
        return None

    url = f"{KIE_API_BASE}/api/v1/jobs/createTask"
    
    payload = json.dumps({
        "model": KIE_MODEL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "nsfw_checker": False,
            "enable_pro": enable_pro
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
            if data.get("code") == 200 and data.get("data", {}).get("taskId"):
                task_id = data["data"]["taskId"]
                print(f"✅ Image task created: {task_id}")
                return task_id
            else:
                print(f"❌ Task creation failed: {data.get('msg', 'Unknown error')}")
                return None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ API Error {e.code}: {error_body}")
        return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None


def get_task_status(task_id):
    """
    Query task status and results.
    
    Returns:
        dict with 'state' and 'resultUrls' if successful
    """
    api_key = get_api_key()
    if not api_key:
        return None

    url = f"{KIE_API_BASE}/api/v1/jobs/recordInfo?taskId={task_id}"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

            if data.get("code") != 200:
                return {"state": "error", "error": data.get("msg", "Unknown error")}

            task_data = data.get("data", {})
            state = task_data.get("state", "unknown")

            result = {"state": state}

            # Parse result URLs if successful
            if state == "success" and task_data.get("resultJson"):
                try:
                    result_json = json.loads(task_data["resultJson"])
                    result["resultUrls"] = result_json.get("resultUrls", [])
                except json.JSONDecodeError:
                    result["resultUrls"] = []

            # Include error info if failed
            if state == "fail":
                result["error"] = task_data.get("failMsg", "Generation failed")
                result["errorCode"] = task_data.get("failCode", "")

            return result
    except Exception as e:
        return {"state": "error", "error": str(e)}


def wait_for_completion(task_id, max_attempts=MAX_POLL_ATTEMPTS):
    """
    Poll task until completion.
    
    Returns:
        Image URL if successful, None otherwise
    """
    print(f"⏳ Waiting for image generation (task: {task_id})...")

    for attempt in range(1, max_attempts + 1):
        result = get_task_status(task_id)
        
        if not result:
            print(f"❌ Failed to query task status")
            return None

        state = result.get("state")

        if state == "success":
            urls = result.get("resultUrls", [])
            if urls:
                image_url = urls[0]
                print(f"✅ Image generated: {image_url}")
                return image_url
            else:
                print(f"❌ Task succeeded but no URLs returned")
                return None
        elif state == "fail":
            print(f"❌ Task failed: {result.get('error', 'Unknown error')}")
            return None
        elif state == "error":
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            return None
        else:
            # Still processing (waiting, queuing, generating)
            if attempt % 6 == 0:  # Log every 30 seconds
                print(f"   Still {state}... (attempt {attempt}/{max_attempts})")
            time.sleep(POLL_INTERVAL)

    print(f"❌ Timeout after {max_attempts * POLL_INTERVAL}s")
    return None


def generate_image_from_post(post_content, hook="", topic=""):
    """
    Generate an image prompt from LinkedIn post content and create image.
    
    Args:
        post_content: Full LinkedIn post text
        hook: Post hook line
        topic: Post topic
    
    Returns:
        Image URL if successful, None otherwise
    """
    # Build a visual prompt from the post content
    prompt = build_image_prompt(post_content, hook, topic)
    
    if not prompt:
        print("❌ Could not generate image prompt")
        return None
    
    print(f"🎨 Image prompt: {prompt[:100]}...")
    
    # Submit task
    task_id = create_image_task(prompt, aspect_ratio="3:2")
    if not task_id:
        return None
    
    # Wait for completion
    return wait_for_completion(task_id)


def build_image_prompt(post_content, hook="", topic=""):
    """
    Create an image generation prompt from LinkedIn post content.
    Generates diverse, context-specific visual styles.
    """
    # Use AI to generate a unique image prompt (with short timeout to avoid hanging)
    try:
        result = subprocess.run(
            [
                "openclaw", "agent",
                "--message", f"""Create a UNIQUE image prompt (max 200 chars) for this LinkedIn post. Do NOT use "Professional LinkedIn post image". Be creative and visual.

Hook: {hook}
Topic: {topic}

Output ONLY the prompt.""",
                "--timeout", "15",
            ],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0 and result.stdout.strip():
            prompt = result.stdout.strip()[:500]
            # Validate it's not the generic style we're trying to avoid
            if "Professional LinkedIn" not in prompt:
                return prompt
    except Exception:
        pass

    # Create modern flat vector editorial illustration prompt specific to the post topic
    import hashlib
    
    # Analyze post content to determine the specific topic elements
    content_lower = (post_content + " " + hook + " " + topic).lower()
    hook_lower = hook.lower()
    
    # Build topic-specific visual elements based on post content
    # Each prompt must be uniquely specific to the post
    
    # Extract key metrics/numbers for visual context
    import re
    dollar_amounts = re.findall(r'\$[\d,.]+(?:/\w+)?', post_content + " " + hook)
    percentages = re.findall(r'\d+%', post_content + " " + hook)
    time_refs = re.findall(r'\d+\s*(?:minutes?|hours?|days?|weeks?|months?)', content_lower)
    
    # Determine topic type and build specific scene description
    # IMPORTANT: Check specific topics BEFORE generic time/efficiency checks
    if 'bookkeeper' in hook_lower or 'bookkeeping' in hook_lower or 'accounting' in hook_lower:
        topic_desc = f"AI-powered bookkeeping automation, showing a modern accounting dashboard with bank feeds, transaction categorization, and reconciliation status, financial reports (P&L, balance sheet) being generated automatically, bookkeeper reviewing AI-suggested entries, clean office environment"
    elif 'email' in hook_lower or 'inbox' in hook_lower:
        topic_desc = f"email automation agent, showing a professional inbox with AI-drafted responses, email templates being applied automatically, follow-up sequences scheduling themselves, time saved metric displayed, modern office with clean desk"
    elif 'hr' in hook_lower or 'hiring' in hook_lower or 'resume' in hook_lower or 'human resources' in hook_lower:
        topic_desc = f"HR automation with AI agent, showing recruitment pipeline with AI-screened candidates, interview scheduling calendar, employee self-service portal for policy questions, onboarding checklist being completed automatically, modern HR office"
    elif 'code review' in hook_lower or ('code' in hook_lower and 'engineer' in hook_lower):
        topic_desc = f"software code review cost comparison, showing a developer reviewing code on a monitor with AI assistant suggesting optimizations, cost metrics displayed ({dollar_amounts[0] if dollar_amounts else '$48'} human vs {dollar_amounts[1] if len(dollar_amounts) > 1 else '$0.72'} AI), modern tech office environment"
    elif 'support team' in hook_lower or 'ticket' in hook_lower or 'customer service' in hook_lower:
        topic_desc = f"customer support cost analysis, showing a modern help desk environment with agents handling tickets, dashboard displaying cost-per-ticket metrics ({dollar_amounts[0] if dollar_amounts else '$4.18'} human vs {dollar_amounts[1] if len(dollar_amounts) > 1 else '$0.46'} AI), resolution rates, and team comparison"
    elif 'marketing' in hook_lower or 'content' in hook_lower:
        topic_desc = f"marketing team time savings and automation, showing a marketing professional reviewing content calendar and campaign analytics dashboard, automated scheduling tools, social media management interface, time saved ({time_refs[0] if time_refs else '23 hours'} per week recovered)"
    elif 'roi' in hook_lower or 'return' in hook_lower:
        roi_val = percentages[0] if percentages else '171%'
        fail_val = percentages[1] if len(percentages) > 1 else '40%'
        topic_desc = f"AI implementation ROI analysis, showing business executives reviewing quarterly ROI dashboard with {roi_val} return metrics, implementation success vs failure rates ({fail_val} failure), cost-benefit comparison charts, modern boardroom setting"
    elif 'market' in hook_lower and ('growing' in hook_lower or 'growth' in hook_lower or 'billion' in hook_lower):
        topic_desc = f"AI agents market growth trajectory, showing analysts reviewing market expansion charts with growth projections ({percentages[0] if percentages else '46%'} annual growth), industry trend lines, market size visualizations ($8B to $251B), strategic planning session"
    elif 'employee' in hook_lower or ('agent' in hook_lower and 'ai' in hook_lower):
        topic_desc = f"AI agent augmenting human workforce, showing office environment where AI handles routine tasks while employees focus on strategic work, dashboard showing productivity gains, human-AI collaboration, team efficiency metrics"
    elif 'minute' in hook_lower or 'hour' in hook_lower:
        time_val = time_refs[0] if time_refs else '40 minutes'
        topic_desc = f"process time savings comparison, showing professional comparing manual vs automated workflow timelines, efficiency dashboard displaying time reduced ({time_val} per interaction), before/after metrics, modern office setting"
    elif 'app' in hook_lower or 'software' in hook_lower:
        topic_desc = f"software applications integrating AI capabilities, showing product team reviewing app performance dashboard with AI feature adoption metrics, user engagement analytics, feature roadmap, modern tech office"
    elif 'workflow' in hook_lower or 'automated' in hook_lower or 'automation' in hook_lower:
        topic_desc = f"business workflow automation setup, showing professional configuring automated processes with visual flowcharts, efficiency gains dashboard, implementation timeline, modern office environment"
    elif 'day' in hook_lower and any(c.isdigit() for c in hook_lower.split('day')[0][-3:]):
        topic_desc = f"report generation time transformation, showing professional viewing automated report system, timeline comparison ({time_refs[0] if time_refs else '15 days'} to {time_refs[1] if len(time_refs) > 1 else '35 minutes'}), efficiency metrics, modern workspace"
    else:
        topic_desc = f"business technology and automation, showing modern office environment with performance metrics dashboard, team collaboration, efficiency visualization, professional workspace"
    
    # Build the complete prompt using the documented style
    prompt = f"""Create a modern flat vector editorial illustration about {topic_desc}.

Style requirements:
* Clean vector artwork with smooth shapes, crisp lines, and scalable SVG-quality graphics.
* Semi-flat design with subtle gradients, soft shadows, and gentle highlights that add depth without becoming photorealistic.
* Minimal texture and visual clutter.
* Professional, polished, and visually engaging composition.
* Modern color palette with balanced contrast and harmonious gradients.
* Clear visual storytelling that explains or represents the topic at a glance.
* Human-centered scenes, relevant objects, symbols, and environments that naturally illustrate the subject matter.
* Consistent proportions, clean geometry, and friendly editorial-style characters when appropriate.
* High-quality infographic-inspired design with strong visual hierarchy.
* Background elements should support the narrative without distracting from the main subject.
* No photorealism, no 3D rendering, no excessive detail, no stock-photo appearance.

Composition:
Illustrate {topic_desc} in a way that is informative, visually appealing, and easy to understand. The scene should communicate the key idea through visual metaphors, relevant activities, technology, people, processes, or environments associated with the topic.

Output:
Premium flat vector editorial illustration, modern SaaS-style artwork, publication-ready, professional, clean, high resolution, wide-format composition."""
    
    return prompt


if __name__ == "__main__":
    # Test mode
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Testing Kie.ai image generation...")
        test_prompt = "A modern office desk with a laptop showing AI analytics dashboard, clean minimalist style, professional lighting"
        task_id = create_image_task(test_prompt)
        if task_id:
            url = wait_for_completion(task_id)
            if url:
                print(f"\n🎉 Test successful! Image URL: {url}")
            else:
                print("\n❌ Test failed - no URL returned")
        else:
            print("\n❌ Test failed - could not create task")
    else:
        print("Usage: python kie_image.py test")
