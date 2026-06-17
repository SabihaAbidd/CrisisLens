import json
from PIL import Image
from crewai import Agent, Task, Crew
from src.config import gemini_model, llm


def _fallback_scene(location: str, description: str = "") -> dict:
    signal = f"{location} {description}".lower()
    incident_type = "Public hazard"
    hazard_objects = ["reported hazard"]
    if "manhole" in signal or "open hole" in signal or "hole" in signal:
        incident_type = "Open Manhole"
        hazard_objects = ["open manhole", "road opening", "unprotected perimeter"]
    elif "sewage" in signal or "drain" in signal or "wastewater" in signal:
        incident_type = "Sewage Overflow"
        hazard_objects = ["sewage overflow", "contaminated water"]
    elif "wire" in signal or "electric" in signal:
        incident_type = "Unsafe Electric Wire"
        hazard_objects = ["electric wire", "public safety hazard"]

    return {
        "incident_type": incident_type,
        "scene_description": description or f"Citizen reported a {incident_type.lower()} at {location}.",
        "hazard_objects": hazard_objects,
        "people_visible": "Unknown",
        "environment": "Outdoor",
        "confidence": 70,
    }


def analyze_scene(image_path: str, location: str, description: str = "") -> dict:
    """
    Analyzes an emergency scene image and location using Gemini multimodal
    and validates the assessment with a CrewAI validator agent.
    """
    # 1. Opens the image using Pillow
    img = Image.open(image_path)

    # 2. Sends the image directly to Gemini multimodal
    prompt = f"""
You are an emergency scene analyst.
Location: {location}
User description: {description if description else 'None provided'}

Analyze this image carefully and return ONLY a raw JSON
object with no markdown and no explanation:
{{
  "incident_type": "e.g. Road accident / Open manhole /
                    Fire / Flood / Fallen tree / Gas leak",
  "scene_description": "2 sentences of what you see exactly",
  "hazard_objects": ["list", "of", "objects", "visible"],
  "people_visible": "a number or Unknown",
  "environment": "Indoor / Outdoor / Road / Building",
  "confidence": integer from 0 to 100
}}
"""
    try:
        response = gemini_model.generate_content([prompt, img])
    except Exception as e:
        print(f"[Agent 1/4] Gemini scene analysis failed, using fallback: {e}")
        return _fallback_scene(location, description)

    # 3. Strip any accidental markdown from response.text
    raw = response.text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    # 4. Parse as JSON and return the dict if JSON parsing fails raise ValueError
    try:
        scene_data = json.loads(raw)
    except Exception as e:
        raise ValueError(f"Scene Analyst failed to parse JSON. Raw output: {raw}") from e

    # 5. Print confirmation of raw analysis
    print(f"[Agent 1/4] Scene analysis done: {scene_data['incident_type']}")

    # Wrap validation logic inside CrewAI validator agent
    validator = Agent(
        role="Scene Analysis Validator",
        goal="Confirm the scene assessment is accurate and complete",
        backstory="""You are a senior emergency analyst who reviews
        junior analysts' scene reports and confirms or corrects them.
        You ensure nothing important is missed.""",
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    validation_task = Task(
        description=f"""Review this scene assessment and confirm it
        is accurate. If anything seems wrong or missing, correct it.
        Return the same JSON structure with any corrections applied.
        
        Scene data to review: {json.dumps(scene_data)}
        Location: {location}
        
        Return ONLY raw JSON, no markdown:
        {{
          "incident_type": "confirmed or corrected type",
          "scene_description": "confirmed or improved description",
          "hazard_objects": ["confirmed list"],
          "people_visible": "confirmed number or Unknown",
          "environment": "confirmed environment",
          "confidence": integer 0 to 100
        }}""",
        agent=validator,
        expected_output="Raw JSON scene assessment"
    )
    
    crew = Crew(agents=[validator], tasks=[validation_task], verbose=True)
    try:
        result = crew.kickoff()
    except Exception as e:
        print(f"[Agent 1/4] Scene validation failed, using initial scene data: {e}")
        return scene_data
    
    validated_raw = result.raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(validated_raw)
    except Exception:
        return scene_data  # fall back to original if validation fails
