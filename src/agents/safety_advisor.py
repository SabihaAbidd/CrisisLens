import json
from crewai import Agent, Task, Crew
from src.config import llm


def _fallback_advice(scene_data: dict, risk_data: dict) -> dict:
    incident_type = scene_data.get("incident_type", "public hazard")
    return {
        "immediate_steps": [
            "Keep people away from the affected area.",
            "Warn pedestrians, motorcyclists, and drivers before they reach the hazard.",
            "Place a visible marker nearby only if it is safe to do so.",
            "Share the exact location with the responsible civic authority.",
        ],
        "do_not_do": [
            f"Do not attempt to repair the {incident_type.lower()} yourself.",
            "Do not let children or motorcycles near the hazard.",
        ],
        "authority_to_contact": "Relevant civic authority",
        "authority_number": "Local helpline",
        "bystander_role": "Stay at a safe distance and warn others until the area is secured.",
    }


def get_advice(scene_data: dict, risk_data: dict) -> dict:
    """
    Takes scene data and risk data and produces practical safety advice
    for ordinary Pakistani citizens during an emergency.
    """
    # 1. Create a CrewAI Agent
    advisor = Agent(
        role="Public Safety Advisor",
        goal="""Give clear, practical safety instructions that
       ordinary Pakistani citizens can follow immediately during
       an emergency — no jargon, no complicated steps.""",
        backstory="""You are a public safety educator who has
       trained volunteers for Rescue 1122, Edhi Foundation, and
       university emergency response teams across Pakistan. You
       write advice that panicked people can actually follow.
       You know Pakistan's emergency numbers by heart.""",
        llm=llm,
        verbose=True,
        allow_delegation=False
    )

    # 2. Create a Task
    task = Task(
        description=f"""Generate safety advice for this emergency.
       
       Scene: {json.dumps(scene_data)}
       Risk assessment: {json.dumps(risk_data)}
       
       Pakistan emergency numbers:
       - Rescue: 1122
       - Police: 15
       - Fire Brigade: 16
       - Ambulance: 115
       - Edhi Foundation: 0800-36434
       
       Return ONLY a raw JSON object, no markdown:
       {{
         "immediate_steps": [
           "Step 1 — clear action",
           "Step 2 — clear action",
           "Step 3 — clear action",
           "Step 4 — clear action"
         ],
         "do_not_do": [
           "Do NOT move injured persons",
           "Do NOT block the rescue path"
         ],
         "authority_to_contact": "Rescue 1122 — call immediately",
         "authority_number": "1122",
         "bystander_role": "One sentence on what nearby
                            people should do right now"
       }}""",
        agent=advisor,
        expected_output="Raw JSON safety advice"
    )

    # 3. Run crew
    crew = Crew(agents=[advisor], tasks=[task], verbose=True)
    try:
        result = crew.kickoff()
    except Exception as e:
        print(f"[Agent 3/4] Safety advisor failed, using fallback: {e}")
        return _fallback_advice(scene_data, risk_data)

    # Strip markdown, parse JSON, and return dict
    raw = result.raw.strip()
    raw_clean = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw_clean)
    except Exception as e:
        print(f"[Agent 3/4] Safety advisor parse failed, using fallback: {e}")
        return _fallback_advice(scene_data, risk_data)

    # 4. Print confirmation
    print(f"[Agent 3/4] Safety advice ready. Contact: {data['authority_to_contact']}")

    return data
