import json
import os
import sys

# Ensure project root is in sys.path for direct execution
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.agents import analyze_scene, assess_risk, get_advice, transcribe_voice, write_report
from src.agents.dispatcher_agent import _resolve_authority, dispatch_report


def _joined_text(*parts):
    values = []
    for part in parts:
        if isinstance(part, list):
            values.extend(str(item) for item in part)
        elif part:
            values.append(str(part))
    return " ".join(values).lower()


def _infer_hazard(description, scene_data, location=""):
    signal = _joined_text(
        description,
        location,
        scene_data.get("incident_type"),
        scene_data.get("scene_description"),
        scene_data.get("hazard_objects"),
    )

    if any(word in signal for word in ["sewage", "drain", "overflow", "wastewater"]) and any(
        word in signal for word in ["manhole", "open hole", "hole", "pit"]
    ):
        return {
            "incident_type": "Sewage Spill with Open Road Hole",
            "risk_level": "Critical",
            "urgency": "Immediate",
            "authority_to_contact": "WASA Lahore and Metropolitan Corporation Lahore",
            "authority_number": "Helpline / emergency civic dispatch",
            "who_is_at_risk": ["pedestrians", "motorcyclists", "drivers", "children"],
        }

    if any(word in signal for word in ["manhole", "open hole", "hole", "pit"]):
        return {
            "incident_type": "Open Manhole",
            "risk_level": "High",
            "urgency": "Immediate",
            "authority_to_contact": "Metropolitan Corporation Lahore / WASA Lahore",
            "authority_number": "Helpline / emergency civic dispatch",
            "who_is_at_risk": ["pedestrians", "motorcyclists", "drivers", "children"],
        }

    if any(word in signal for word in ["sewage", "drain", "overflow", "wastewater"]):
        return {
            "incident_type": "Sewage Overflow",
            "risk_level": "High",
            "urgency": "Immediate",
            "authority_to_contact": "WASA Lahore",
            "authority_number": "WASA helpline",
            "who_is_at_risk": ["pedestrians", "drivers", "residents", "shopkeepers"],
        }

    if any(word in signal for word in ["electric", "wire", "power line", "electrocution"]):
        return {
            "incident_type": "Unsafe Electric Wire",
            "risk_level": "Critical",
            "urgency": "Immediate",
            "authority_to_contact": "Rescue 1122 and LESCO",
            "authority_number": "1122",
            "who_is_at_risk": ["pedestrians", "drivers", "residents", "utility workers"],
        }

    if any(word in signal for word in ["flood", "flooding", "waterlogged"]):
        return {
            "incident_type": "Flooding",
            "risk_level": "High",
            "urgency": "Immediate",
            "authority_to_contact": "WASA Lahore",
            "authority_number": "WASA helpline",
            "who_is_at_risk": ["pedestrians", "drivers", "residents"],
        }

    if "tree" in signal:
        return {
            "incident_type": "Fallen Tree",
            "risk_level": "High",
            "urgency": "Immediate",
            "authority_to_contact": "Parks and Horticulture Authority and Rescue 1122",
            "authority_number": "1122",
            "who_is_at_risk": ["drivers", "pedestrians", "utility workers"],
        }

    return None


def _resolve_authority_hint(location, scene_data, description):
    signal_text = " ".join(
        [
            description or "",
            scene_data.get("incident_type", ""),
            scene_data.get("scene_description", ""),
        ]
    ).strip()
    return _resolve_authority(location, scene_data.get("incident_type", "emergency"), signal_text)


def _normalize_scene(scene_data, inferred):
    if not inferred:
        return scene_data
    normalized = dict(scene_data)
    normalized["incident_type"] = inferred["incident_type"]
    normalized["confidence"] = max(int(scene_data.get("confidence", 85)), 85)
    return normalized


def _normalize_risk(risk_data, inferred):
    normalized = dict(risk_data)
    if inferred:
        normalized["risk_level"] = inferred["risk_level"]
        normalized["urgency"] = inferred["urgency"]
        normalized["who_is_at_risk"] = inferred["who_is_at_risk"]
        normalized["is_life_threatening"] = inferred["risk_level"] == "Critical"
    normalized.setdefault("risk_reason", "The hazard can cause immediate injury and disrupt public movement.")
    normalized.setdefault("estimated_impact_radius", "5 to 20 meters")
    return normalized


def _normalize_advice(advice_data, inferred, authority_hint=None):
    normalized = dict(advice_data)
    if inferred:
        normalized["authority_to_contact"] = inferred["authority_to_contact"]
        normalized["authority_number"] = inferred["authority_number"]
    if authority_hint and authority_hint.get("authority_name"):
        normalized["authority_to_contact"] = authority_hint["authority_name"]
        if authority_hint.get("authority_phone"):
            normalized["authority_number"] = authority_hint["authority_phone"]
    normalized.setdefault(
        "immediate_steps",
        [
            "Keep people away from the affected area.",
            "Slow traffic and redirect vehicles if safe to do so.",
            "Share the exact location with the authority dispatcher.",
            "Wait for municipal or emergency crews to secure the scene.",
        ],
    )
    normalized.setdefault(
        "do_not_do",
        [
            "Do not attempt repairs without safety barriers and equipment.",
            "Do not allow children or motorcycles near the hazard.",
        ],
    )
    normalized.setdefault("bystander_role", "Warn nearby people and keep the area clear until responders arrive.")
    return normalized


def _build_consistent_report(report_data, scene_data, risk_data, advice_data, location, description):
    full_report = dict(report_data.get("full_report", {}))
    full_report["incident_type"] = scene_data.get("incident_type", full_report.get("incident_type", "Public hazard"))
    full_report["risk_level"] = risk_data.get("risk_level", full_report.get("risk_level", "High"))
    full_report["location"] = location
    full_report["scene_description"] = scene_data.get("scene_description", full_report.get("scene_description", ""))
    full_report["who_is_at_risk"] = risk_data.get("who_is_at_risk", full_report.get("who_is_at_risk", []))
    full_report["is_life_threatening"] = risk_data.get("is_life_threatening", full_report.get("is_life_threatening", False))
    full_report["urgency"] = risk_data.get("urgency", full_report.get("urgency", "Immediate"))
    full_report["immediate_steps"] = advice_data.get("immediate_steps", full_report.get("immediate_steps", []))
    full_report["do_not_do"] = advice_data.get("do_not_do", full_report.get("do_not_do", []))
    full_report["authority_to_contact"] = advice_data.get(
        "authority_to_contact", full_report.get("authority_to_contact", "Relevant civic authority")
    )
    full_report["authority_number"] = advice_data.get(
        "authority_number", full_report.get("authority_number", "Local helpline")
    )
    full_report["confidence"] = scene_data.get("confidence", full_report.get("confidence", 90))

    summary_bits = []
    if description:
        summary_bits.append(description.strip())
    if scene_data.get("scene_description"):
        summary_bits.append(scene_data["scene_description"].strip())
    evidence_line = " ".join(summary_bits).strip()

    report_summary = (
        f"This report concerns a {full_report['incident_type'].lower()} at {location}. "
        f"The hazard has been assessed as {full_report['risk_level'].lower()} risk and poses danger to "
        f"{', '.join(full_report['who_is_at_risk'])}. "
        f"Immediate inspection, barricading, cleanup, and repair are requested from {full_report['authority_to_contact']}."
    )
    if evidence_line:
        report_summary += f" Reporter notes: {evidence_line}"

    public_alert_english = (
        f"{full_report['incident_type']} reported at {location}. "
        f"Risk level is {full_report['risk_level']}. Avoid the area and contact {full_report['authority_to_contact']}."
    )

    normalized = dict(report_data)
    normalized["report_title"] = f"{full_report['risk_level']} - {full_report['incident_type']} at {location}"
    normalized["report_summary"] = report_summary
    normalized["public_alert_english"] = public_alert_english
    normalized["public_alert_urdu"] = report_data.get(
        "public_alert_urdu",
        "عوامی خطرہ رپورٹ ہوا ہے۔ جگہ سے دور رہیں اور متعلقہ ادارے کو فوری اطلاع دیں۔",
    )
    normalized["full_report"] = full_report
    return normalized


def _replace_authority_references(text, authority_name, authority_phone):
    if not text:
        return text
    replacements = [
        "Rescue 1122 - call immediately",
        "Rescue 1122",
        "1122",
        "WASA Lahore and Metropolitan Corporation Lahore",
        "Metropolitan Corporation Lahore / WASA Lahore",
        "WASA Lahore",
    ]
    updated = str(text)
    replacement_value = authority_name
    if authority_phone:
        replacement_value = f"{authority_name} ({authority_phone})"
    for item in replacements:
        updated = updated.replace(item, replacement_value)
    return updated


def _apply_dispatch_authority(report, dispatch_data, location):
    full = dict(report.get("full_report", {}))
    authority_name = dispatch_data.get("authority_name") or full.get("authority_to_contact")
    authority_phone = dispatch_data.get("authority_phone") or full.get("authority_number")
    if not authority_name:
        report["full_report"] = full
        return report

    full["authority_to_contact"] = authority_name
    if authority_phone:
        full["authority_number"] = authority_phone

    immediate_steps = full.get("immediate_steps", [])
    if isinstance(immediate_steps, list):
        full["immediate_steps"] = [
            _replace_authority_references(step, authority_name, authority_phone) for step in immediate_steps
        ]

    do_not_do = full.get("do_not_do", [])
    if isinstance(do_not_do, list):
        full["do_not_do"] = [
            _replace_authority_references(step, authority_name, authority_phone) for step in do_not_do
        ]

    report_summary = (
        f"This report concerns a {full.get('incident_type', 'public hazard').lower()} at {location}. "
        f"The hazard has been assessed as {full.get('risk_level', 'high').lower()} risk and poses danger to "
        f"{', '.join(full.get('who_is_at_risk', []))}. "
        f"Immediate inspection, barricading, cleanup, and repair are requested from {authority_name}."
    )
    scene_description = full.get("scene_description")
    if scene_description:
        report_summary += f" Field observation: {scene_description}"

    report["report_summary"] = report_summary
    report["public_alert_english"] = (
        f"{full.get('incident_type', 'Hazard')} reported at {location}. "
        f"Risk level is {full.get('risk_level', 'High')}. Avoid the area and contact {authority_name}."
    )
    report["report_title"] = f"{full.get('risk_level', 'High')} - {full.get('incident_type', 'Hazard')} at {location}"
    report["full_report"] = full
    return report


def _apply_authority_hint(report, authority_hint, location):
    if not authority_hint or not authority_hint.get("authority_name"):
        return report

    full = dict(report.get("full_report", {}))
    authority_name = authority_hint["authority_name"]
    authority_phone = authority_hint.get("authority_phone")

    full["authority_to_contact"] = authority_name
    if authority_phone:
        full["authority_number"] = authority_phone

    if isinstance(full.get("immediate_steps"), list):
        full["immediate_steps"] = [
            _replace_authority_references(step, authority_name, authority_phone)
            for step in full["immediate_steps"]
        ]

    if isinstance(full.get("do_not_do"), list):
        full["do_not_do"] = [
            _replace_authority_references(step, authority_name, authority_phone)
            for step in full["do_not_do"]
        ]

    who = full.get("who_is_at_risk", [])
    who_text = ", ".join(who) if isinstance(who, list) else str(who)
    report["report_summary"] = (
        f"This report concerns a {full.get('incident_type', 'public hazard').lower()} at {location}. "
        f"The hazard has been assessed as {full.get('risk_level', 'high').lower()} risk and poses danger to {who_text}. "
        f"Immediate inspection, barricading, and repair are requested from {authority_name}."
    )
    report["public_alert_english"] = (
        f"{full.get('incident_type', 'Hazard')} reported at {location}. "
        f"Risk level is {full.get('risk_level', 'High')}. Avoid the area and contact {authority_name}."
    )
    report["full_report"] = full
    return report


def run_pipeline(image_path: str, location: str, description: str = "", audio_path: str = None) -> dict:
    """
    Runs the full CrisisLens emergency response pipeline end-to-end.
    """
    if audio_path:
        step = 0
        try:
            print("Processing voice note...")
            voice_data = transcribe_voice(audio_path)

            description = (description + " " + voice_data["translation"]).strip()

            if voice_data.get("location_mentioned") and voice_data["location_mentioned"] != "None":
                location = location + " (voice note mentioned: " + voice_data["location_mentioned"] + ")"

            print("Voice note processed and merged with scene data.")
        except Exception as e:
            raise RuntimeError(f"Pipeline failed at step {step}: {str(e)}") from e

    step = 1
    try:
        print("Step 1/4 - Scene Analyst is examining the image...")
        scene_data = analyze_scene(image_path, location, description)
    except Exception as e:
        raise RuntimeError(f"Pipeline failed at step {step}: {str(e)}") from e

    inferred = _infer_hazard(description, scene_data, location)
    scene_data = _normalize_scene(scene_data, inferred)
    authority_hint = _resolve_authority_hint(location, scene_data, description)

    step = 2
    try:
        print("Step 2/4 - Risk Assessor is evaluating danger level...")
        risk_data = assess_risk(scene_data, location)
    except Exception as e:
        raise RuntimeError(f"Pipeline failed at step {step}: {str(e)}") from e

    risk_data = _normalize_risk(risk_data, inferred)

    step = 3
    try:
        print("Step 3/4 - Safety Advisor is generating guidance...")
        advice_data = get_advice(scene_data, risk_data)
    except Exception as e:
        raise RuntimeError(f"Pipeline failed at step {step}: {str(e)}") from e

    advice_data = _normalize_advice(advice_data, inferred, authority_hint)

    step = 4
    try:
        print("Step 4/4 - Report Writer is composing the report...")
        report_data = write_report(scene_data, risk_data, advice_data, location)
    except Exception as e:
        raise RuntimeError(f"Pipeline failed at step {step}: {str(e)}") from e

    report = _build_consistent_report(report_data, scene_data, risk_data, advice_data, location, description)
    report = _apply_authority_hint(report, authority_hint, location)

    step = 5
    try:
        print("Step 5/5 - Dispatch Agent searching for authorities and sending report...")
        dispatch_data = dispatch_report(report, location)
        report["dispatch"] = dispatch_data
        report = _apply_dispatch_authority(report, dispatch_data, location)
        print(f"Step 5/5 - Dispatched to: {dispatch_data['authority_name']}")
    except Exception as e:
        raise RuntimeError(f"Pipeline failed at step {step}: {str(e)}") from e

    return report


if __name__ == "__main__":
    TEST_IMAGE = "demo_assets/test_scene.jpg"
    TEST_LOCATION = "Gulberg Main Boulevard, Lahore"
    TEST_DESCRIPTION = "There is water on the road and cars cannot pass"

    if not os.path.exists(TEST_IMAGE):
        print("ERROR: Put a test image at demo_assets/test_scene.jpg first")
        sys.exit(1)

    print("Running CrisisLens pipeline test...")
    result = run_pipeline(image_path=TEST_IMAGE, location=TEST_LOCATION, description=TEST_DESCRIPTION)
    print("\n" + "=" * 50)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 50)
    print("Pipeline complete. All 4 agents ran successfully.")
