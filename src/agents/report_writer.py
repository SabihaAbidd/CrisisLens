import json
from crewai import Agent, Task, Crew
from src.config import llm

def write_report(scene_data: dict, risk_data: dict, advice_data: dict, location: str) -> dict:
    """
    Takes scene data, risk data, and safety advice, and writes a polished
    emergency report in both English and Urdu.
    """
    # 1. Create a CrewAI Agent
    writer = Agent(
        role="Emergency Report Writer",
        goal="""Write a complete, professional emergency report
       that authorities can act on immediately, plus a short
       public alert in both English and Urdu for sharing
       on WhatsApp.""",
        backstory="""You have written official incident reports
       for Punjab Municipal Authority, FAST University security
       office, and Lahore city complaint portal. You know exactly
       how to phrase things so rescue teams take them seriously.
       You are also fluent in Urdu and write clear, simple Urdu
       that any Pakistani citizen can understand.""",
        llm=llm,
        verbose=True,
        allow_delegation=False
    )

    # 2. Create a Task
    task = Task(
        description=f"""Write the final emergency report using
       all intelligence from the three analysts below.
       
       SCENE DATA: {json.dumps(scene_data)}
       RISK DATA: {json.dumps(risk_data)}
       SAFETY ADVICE: {json.dumps(advice_data)}
       LOCATION: {location}
       
       Return ONLY a raw JSON object, no markdown, no explanation:
       {{
         "report_title": "e.g. Critical — Road Accident on
                          Gulberg Main Boulevard Lahore",
         "report_summary": "Formal 3-sentence paragraph written
                            as an official report ready to paste
                            into a complaint or send to authority",
         "public_alert_english": "Under 80 words. Simple English.
                                  Start with the incident type and
                                  location. Include what to do.
                                  WhatsApp-ready.",
         "public_alert_urdu": "Same alert in simple Urdu. Under
                               80 words. Use simple everyday Urdu
                               that anyone can understand.",
         "full_report": {{
           "incident_type": "from scene_data",
           "risk_level": "from risk_data",
           "location": "{location}",
           "scene_description": "from scene_data",
           "who_is_at_risk": "from risk_data",
           "is_life_threatening": "from risk_data",
           "urgency": "from risk_data",
           "immediate_steps": "from advice_data",
           "do_not_do": "from advice_data",
           "authority_to_contact": "from advice_data",
           "authority_number": "from advice_data",
           "confidence": "from scene_data"
         }}
       }}""",
        agent=writer,
        expected_output="Raw JSON final emergency report"
    )

    # 3. Run crew
    crew = Crew(agents=[writer], tasks=[task], verbose=True)
    result = crew.kickoff()

    # Strip markdown, parse JSON, and return dict
    raw = result.raw.strip()
    raw_clean = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw_clean)
    except Exception as e:
        raise ValueError(f"Report Writer failed to parse. Raw: {result.raw}") from e

    # 4. Print completion
    print(f"[Agent 4/4] Report complete: {data['report_title']}")

    return data
