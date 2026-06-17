import json
from crewai import Agent, Task, Crew
from src.config import llm


def _fallback_report(scene_data: dict, risk_data: dict, advice_data: dict, location: str) -> dict:
    incident_type = scene_data.get("incident_type", "Public Hazard")
    risk_level = risk_data.get("risk_level", "High")
    authority = advice_data.get("authority_to_contact", "Relevant civic authority")
    summary = (
        f"A {incident_type.lower()} has been reported at {location}. "
        f"The issue is assessed as {risk_level.lower()} risk because it may endanger nearby citizens and traffic. "
        f"Immediate inspection, barricading, and repair are requested from {authority}."
    )
    return {
        "report_title": f"{risk_level} - {incident_type} at {location}",
        "report_summary": summary,
        "public_alert_english": (
            f"{incident_type} reported at {location}. Risk level is {risk_level}. "
            "Avoid the area and warn others nearby."
        ),
        "public_alert_urdu": "عوامی خطرہ رپورٹ ہوا ہے۔ جگہ سے دور رہیں اور متعلقہ ادارے کو فوری اطلاع دیں۔",
        "full_report": {
            "incident_type": incident_type,
            "risk_level": risk_level,
            "location": location,
            "scene_description": scene_data.get("scene_description", ""),
            "who_is_at_risk": risk_data.get("who_is_at_risk", []),
            "is_life_threatening": risk_data.get("is_life_threatening", False),
            "urgency": risk_data.get("urgency", "Immediate"),
            "immediate_steps": advice_data.get("immediate_steps", []),
            "do_not_do": advice_data.get("do_not_do", []),
            "authority_to_contact": authority,
            "authority_number": advice_data.get("authority_number", "Local helpline"),
            "confidence": scene_data.get("confidence", 70),
        },
    }


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
    try:
        result = crew.kickoff()
    except Exception as e:
        print(f"[Agent 4/4] Report writer failed, using fallback: {e}")
        return _fallback_report(scene_data, risk_data, advice_data, location)

    # Strip markdown, parse JSON, and return dict
    raw = result.raw.strip()
    raw_clean = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw_clean)
    except Exception as e:
        print(f"[Agent 4/4] Report writer parse failed, using fallback: {e}")
        return _fallback_report(scene_data, risk_data, advice_data, location)

    # 4. Print completion
    print(f"[Agent 4/4] Report complete: {data['report_title']}")

    return data
