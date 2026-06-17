import json
from crewai import Agent, Task, Crew
from src.config import llm

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
    result = crew.kickoff()

    # 4. Strip markdown, parse JSON, and return dict
    raw = result.raw.strip()
    raw_clean = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw_clean)
    except Exception as e:
        raise ValueError(f"Risk Assessor failed to parse. Raw: {result.raw}") from e

    # 5. Print status
    print(f"[Agent 2/4] Risk assessed: {data['risk_level']} — {data['urgency']}")

    return data
