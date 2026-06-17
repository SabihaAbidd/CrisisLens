import json
from crewai import Agent, Task, Crew
from src.config import llm


def _fallback_risk(scene_data: dict, location: str) -> dict:
    signal = " ".join(
        [
            str(scene_data.get("incident_type", "")),
            str(scene_data.get("scene_description", "")),
            location or "",
        ]
    ).lower()
    is_critical = any(word in signal for word in ["fire", "gas leak", "electrocution", "trapped", "injured"])
    return {
        "risk_level": "Critical" if is_critical else "High",
        "risk_reason": "The reported hazard can cause immediate injury if people or vehicles enter the affected area.",
        "who_is_at_risk": ["pedestrians", "motorcyclists", "drivers", "children"],
        "is_life_threatening": is_critical,
        "urgency": "Immediate",
        "estimated_impact_radius": "5 to 20 meters",
    }


def assess_risk(scene_data: dict, location: str) -> dict:
    """
    Assesses the risk level, urgency, danger group, and safety impact of an emergency
    scene using a text-based CrewAI agent.
    """
    # 1. Create a CrewAI Agent
    assessor = Agent(
        role="Emergency Risk Assessor",
        goal="""Determine the exact risk level of an emergency
       situation and identify who is in danger.""",
        backstory="""You are a risk assessment specialist who has
       worked with Pakistan's rescue services (1122), civil defense,
       and city municipal authorities. You know exactly what makes
       a situation Low, Medium, High, or Critical risk and you
       never underestimate danger.""",
        llm=llm,
        verbose=True,
        allow_delegation=False
    )

    # 2. Create a Task
    task = Task(
        description=f"""Assess the risk level of this emergency.
       
       Scene report from analyst: {json.dumps(scene_data)}
       Location: {location}
       
       Return ONLY a raw JSON object, no markdown, no explanation:
       {{
         "risk_level": "exactly one of: Low / Medium / High / Critical",
         "risk_reason": "one sentence explaining why this risk level",
         "who_is_at_risk": ["pedestrians", "drivers", "children", etc],
         "is_life_threatening": true or false,
         "urgency": "exactly one of: Immediate / Within the hour / Non-urgent",
         "estimated_impact_radius": "e.g. 5 meters / 50 meters / entire road"
       }}""",
        agent=assessor,
        expected_output="Raw JSON risk assessment"
    )

    # 3. Run the crew
    crew = Crew(agents=[assessor], tasks=[task], verbose=True)
    try:
        result = crew.kickoff()
    except Exception as e:
        print(f"[Agent 2/4] Risk assessor failed, using fallback: {e}")
        return _fallback_risk(scene_data, location)

    # 4. Strip markdown, parse JSON, and return dict
    raw = result.raw.strip()
    raw_clean = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw_clean)
    except Exception as e:
        print(f"[Agent 2/4] Risk assessor parse failed, using fallback: {e}")
        return _fallback_risk(scene_data, location)

    # 5. Print status
    print(f"[Agent 2/4] Risk assessed: {data['risk_level']} — {data['urgency']}")

    return data
