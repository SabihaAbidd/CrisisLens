import json
import os
import re
import smtplib
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import llm


def _serper_search(query: str) -> dict:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return {"ok": False, "error": "SERPER_API_KEY missing", "results": []}

    payload = json.dumps({"q": query, "num": 5}).encode("utf-8")
    request = urllib.request.Request(
        "https://google.serper.dev/search",
        data=payload,
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        organic = data.get("organic", [])
        return {"ok": True, "results": organic[:5]}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "results": []}


def _extract_contact(snippets: str) -> dict:
    # Basic regex backup for extraction
    phone_match = re.search(r"(\+92[\d\s-]{8,}|0\d{2,4}[-\s]?\d{5,8}|1122|118|1334)", snippets)
    email_match = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", snippets)
    whatsapp_match = re.search(r"(\+92[\d\s-]{8,}|92\d{8,}|03\d{9})", snippets)

    phone = phone_match.group(1).strip() if phone_match else None
    email = email_match.group(1).strip() if email_match else None
    whatsapp = whatsapp_match.group(1).strip() if whatsapp_match else None
    if whatsapp:
        whatsapp = "".join(ch for ch in whatsapp if ch.isdigit())
        if whatsapp.startswith("03"):
            whatsapp = "92" + whatsapp[1:]
    return {
        "authority_phone": phone,
        "authority_email": email,
        "authority_whatsapp": whatsapp,
    }


def extract_location_context(location_text: str, gps: dict | None = None) -> dict:
    """
    Uses Gemini/LLM to extract structured location and jurisdiction hints.
    """
    prompt = f"""
    You are a geography expert specialized in Pakistani administrative boundaries.
    Extract the structured location details from this location text.
    Location: "{location_text}"
    GPS Coordinates: {gps}

    Identify the country, province, city, area, neighborhood, landmark/institution, and jurisdiction level (e.g., Municipal Corporation, Cantonment Board, private housing society like DHA or Bahria, campus admin, highway authority, etc.).
    
    Return ONLY a raw JSON object matching this schema, no markdown code blocks or additional text:
    {{
      "country": "Pakistan",
      "province": "province name or None",
      "city": "city name or None",
      "area": "area/town/sector or None",
      "neighborhood": "neighborhood/street/block or None",
      "institution_or_landmark": "landmark name like FAST, NUST, etc. or None",
      "jurisdiction_hint": "municipal | cantonment | housing_society | campus_admin | highway_authority | other",
      "location_confidence": 0.85
    }}
    """
    try:
        response = llm.call(prompt)
        cleaned = str(response).replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except Exception as e:
        print(f"[Extract Location] LLM failed: {e}")
        # Deterministic fallback logic
        city = "Unknown"
        loc_lower = location_text.lower()
        if "lahore" in loc_lower:
            city = "Lahore"
        elif "islamabad" in loc_lower:
            city = "Islamabad"
        elif "karachi" in loc_lower:
            city = "Karachi"
        elif "rawalpindi" in loc_lower:
            city = "Rawalpindi"
            
        hint = "municipal"
        if "fast" in loc_lower or "nust" in loc_lower or "lums" in loc_lower or "university" in loc_lower:
            hint = "campus_admin"
        elif "dha" in loc_lower or "bahria" in loc_lower:
            hint = "housing_society"
        elif "cantt" in loc_lower or "cantonment" in loc_lower:
            hint = "cantonment"
            
        return {
            "country": "Pakistan",
            "province": "Punjab" if city in ["Lahore", "Rawalpindi"] else ("Sindh" if city == "Karachi" else "Federal Capital" if city == "Islamabad" else ""),
            "city": city,
            "area": "",
            "neighborhood": "",
            "institution_or_landmark": "FAST-NUCES" if "fast" in loc_lower else "",
            "jurisdiction_hint": hint,
            "location_confidence": 0.5
        }


def classify_hazard(issue_type: str, description: str, image_summary: str = "") -> dict:
    """
    Uses Gemini/LLM to classify hazard and detect active emergency.
    """
    prompt = f"""
    You are an emergency triage and public safety dispatcher.
    Classify the following incident details to distinguish between a municipal civic hazard and an active emergency.
    
    Issue Type: "{issue_type}"
    Description/Voice Note: "{description}"
    Image Summary: "{image_summary}"
    
    Determine if this is an ACTIVE EMERGENCY. An active emergency requires immediate rescue intervention (injury, trapped person, fire, active electrocution hazard, gas leak, unconscious person, or immediate life-threatening danger). 
    A standard high-risk civic hazard (e.g. open manhole without injury, sewage spill, hanging wire without active spark/electrocution, broken streetlight) is NOT an active emergency.
    
    Return ONLY a raw JSON object matching this schema, no markdown code blocks or additional text:
    {{
      "issue_type": "standardized issue type",
      "issue_category": "civic_infrastructure | sanitation | electricity | road_safety | fire | medical | crime | traffic | other",
      "risk_level": "low | medium | high | critical",
      "is_active_emergency": true/false,
      "emergency_reason": "explanation of emergency or empty string",
      "emergency_keywords_found": ["list of emergency keywords found or empty"]
    }}
    """
    try:
        response = llm.call(prompt)
        cleaned = str(response).replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except Exception as e:
        print(f"[Classify Hazard] LLM failed: {e}")
        # Fallback check
        signal = f"{issue_type} {description} {image_summary}".lower()
        is_emerg = any(word in signal for word in ["injury", "injured", "fell in", "trapped", "fire", "smoke", "accident", "shock", "electrocuted", "unconscious"])
        return {
            "issue_type": issue_type,
            "issue_category": "electricity" if "wire" in signal or "electric" in signal else ("sanitation" if "sewage" in signal or "manhole" in signal else "civic_infrastructure"),
            "risk_level": "critical" if is_emerg else "high",
            "is_active_emergency": is_emerg,
            "emergency_reason": "Bystander reported injury or active threat." if is_emerg else "",
            "emergency_keywords_found": [w for w in ["injury", "trapped", "fire", "accident"] if w in signal]
        }


def build_authority_search_queries(location_context: dict, hazard_context: dict) -> list[str]:
    """
    Generates 5-8 targeted authority discovery search queries.
    """
    queries = []
    city = location_context.get("city") or "Pakistan"
    area = location_context.get("area") or ""
    landmark = location_context.get("institution_or_landmark") or ""
    issue = hazard_context.get("issue_type") or "civic hazard"
    category = hazard_context.get("issue_category") or ""
    
    # Landmark specific queries
    if landmark:
        queries.append(f"{landmark} {city} {issue} complaint authority")
        queries.append(f"{landmark} campus security administration office")
    
    # City level queries
    queries.append(f"{city} {issue} complaint contact helpline")
    queries.append(f"{city} {category} official department complaint")
    
    if area:
        queries.append(f"{area} {city} municipal {issue} maintenance")
        queries.append(f"{area} {city} sewer sewerage authority complaint")
        
    # Search constraints
    queries.append(f"site:*.gov.pk {city} {issue} complaint")
    
    # Issue specific fallbacks
    if "manhole" in issue.lower() or "sewage" in issue.lower():
        queries.append(f"{city} water sanitation sewerage authority WASA contact")
    elif "wire" in issue.lower() or "electric" in issue.lower():
        queries.append(f"{city} electric power distribution utility complaint")
    elif "light" in issue.lower() or "street" in issue.lower():
        queries.append(f"{city} Metropolitan Corporation street light complain")
        
    # Return unique, non-empty queries up to 8
    seen = set()
    result = []
    for q in queries:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            result.append(q)
    return result[:8]


def discover_authority_candidates(search_queries: list[str]) -> list[dict]:
    """
    Uses Serper API to discover authority candidate websites.
    """
    candidates = []
    seen_urls = set()
    # Limit to top 4 search queries to keep runtime reasonable
    for query in search_queries[:4]:
        search_res = _serper_search(query)
        if search_res.get("ok"):
            for result in search_res.get("results", []):
                url = result.get("link")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Determine source type
                source_type = "other"
                url_lower = url.lower()
                if ".gov.pk" in url_lower or ".gov" in url_lower:
                    source_type = "government"
                elif any(domain in url_lower for domain in ["lesco.gov.pk", "iesco.com.pk", "ke.com.pk", "gepco.com.pk", "fesco.com.pk", "mepco.com.pk", "pesco.com.pk", "hesco.gov.pk", "sepco.com.pk"]):
                    source_type = "utility"
                elif any(word in url_lower for word in ["wasa", "water", "sewage", "sanitation"]):
                    source_type = "utility"
                elif any(word in url_lower for word in ["news", "tribune", "dawn", "thenews", "geo", "ary"]):
                    source_type = "news"
                elif ".edu" in url_lower:
                    source_type = "institution"
                
                candidates.append({
                    "title": result.get("title", ""),
                    "url": url,
                    "snippet": result.get("snippet", ""),
                    "source_type": source_type
                })
    return candidates


def rank_authority_candidates(candidates: list[dict], location_context: dict, hazard_context: dict) -> list[dict]:
    """
    Uses LLM scoring plus deterministic source quality checks.
    """
    if not candidates:
        return []
        
    candidates_str = ""
    for idx, c in enumerate(candidates[:15]):
        candidates_str += f"[{idx}] Source Type: {c['source_type']}\nTitle: {c['title']}\nURL: {c['url']}\nSnippet: {c['snippet']}\n\n"
        
    prompt = f"""
    You are a public safety dispatcher. Rank the following candidate websites by their official responsibility and relevance for resolving the hazard described.
    
    Hazard Context:
    - Issue Type: {hazard_context.get('issue_type')}
    - Category: {hazard_context.get('issue_category')}
    - Location: {location_context.get('city')}, {location_context.get('area')}, {location_context.get('institution_or_landmark')}
    - Jurisdiction Hint: {location_context.get('jurisdiction_hint')}
    
    Candidates:
    {candidates_str}
    
    Rank the candidates from highest (most official utility, municipal, or landmark/campus admin site) to lowest (blogs, social media, news). Reject completely irrelevant pages.
    Return ONLY a raw JSON array of indices representing the sorted candidates from best to worst, e.g., [2, 0, 4, 1]. Do not return anything else.
    """
    try:
        response = llm.call(prompt)
        cleaned = str(response).replace("```json", "").replace("```", "").strip()
        ranked_indices = json.loads(cleaned)
        
        ranked_candidates = []
        for idx in ranked_indices:
            if isinstance(idx, int) and 0 <= idx < len(candidates):
                ranked_candidates.append(candidates[idx])
                
        for idx, c in enumerate(candidates):
            if c not in ranked_candidates:
                ranked_candidates.append(c)
                
        return ranked_candidates
    except Exception as e:
        print(f"[Rank Candidates] LLM failed: {e}")
        type_priority = {
            "government": 1,
            "utility": 2,
            "institution": 3,
            "other": 4,
            "news": 5
        }
        return sorted(candidates, key=lambda x: type_priority.get(x["source_type"], 99))


def final_authority_route(location_context: dict, hazard_context: dict, ranked_candidates: list[dict]) -> dict:
    """
    Produces the final routing JSON.
    """
    evidence_str = ""
    for idx, c in enumerate(ranked_candidates[:5]):
        evidence_str += f"Candidate {idx+1}:\nTitle: {c['title']}\nURL: {c['url']}\nSnippet: {c['snippet']}\n\n"
        
    prompt = f"""
    You are a public safety dispatcher. Synthesize the final routing instructions for the following civic hazard/emergency.
    
    Location Context:
    {json.dumps(location_context, indent=2)}
    
    Hazard Context:
    {json.dumps(hazard_context, indent=2)}
    
    Top Search Evidence:
    {evidence_str if evidence_str else "NO SEARCH EVIDENCE AVAILABLE. Use LLM knowledge fallback."}
    
    Determine the primary authority, primary department, secondary authority, emergency contact, routing confidence, and why this routing was chosen.
    
    CRITICAL RULES:
    1. Active Emergency is {hazard_context.get('is_active_emergency')}.
    2. If Active Emergency is TRUE:
       - emergency_contact MUST be "Rescue 1122"
       - should_call_emergency_now = true
       - primary_authority should be the local civic/municipal/utility body responsible for fixing the root cause (e.g. WASA, LESCO, IESCO, CDA, Campus Admin, etc.)
    3. If Active Emergency is FALSE:
       - Rescue 1122 MUST NOT be the primary_authority.
       - should_call_emergency_now = false
       - emergency_contact should say "Rescue 1122 only if injury, trapped person, fire, or immediate danger"
       - primary_authority MUST be the discovered local municipal/civic/utility authority.
    4. If there is NO search evidence or it is low quality, set routing_confidence <= 45.0, and prepend "No official source found. This is the most likely responsible civic authority based on issue type and location. Please verify before submission." to the routing_reason.
    5. Carefully inspect search snippets to find any contact phone numbers, emails, or WhatsApp numbers. Fill them in "primary_phone", "primary_email", and "primary_whatsapp" if found. If not found, leave them as null or use standard numbers if known.
    
    Return ONLY a JSON matching the following schema, no markdown code blocks or additional text:
    {{
      "primary_authority": "Name of primary authority (e.g. WASA Lahore, CDA Islamabad, LESCO, NUST Campus Security, DHA Admin, etc.)",
      "primary_department": "Name of department (e.g. Sewerage Division, Operations, Security Office, etc.)",
      "secondary_authority": "Name of secondary authority or 'None'",
      "emergency_contact": "Rescue 1122 or conditional instructions",
      "should_call_emergency_now": true/false,
      "routing_confidence": percentage float (e.g. 85.0),
      "routing_reason": "Explanation of why this authority was chosen.",
      "evidence_sources": [
        {{
          "title": "source page title",
          "url": "source url",
          "why_relevant": "brief description"
        }}
      ],
      "citizen_action": "Instructions for citizens (e.g. stand back, report via portal, etc.)",
      "authority_message_type": "complaint | emergency_alert | service_request",
      "primary_phone": "phone number string or null",
      "primary_email": "email string or null",
      "primary_whatsapp": "whatsapp number string or null"
    }}
    """
    try:
        response = llm.call(prompt)
        cleaned = str(response).replace("```json", "").replace("```", "").strip()
        result = json.loads(cleaned)
        
        # Verify schema keys exist
        keys = ["primary_authority", "primary_department", "secondary_authority", "emergency_contact", 
                "should_call_emergency_now", "routing_confidence", "routing_reason", "evidence_sources", 
                "citizen_action", "authority_message_type", "primary_phone", "primary_email", "primary_whatsapp"]
        for key in keys:
            if key not in result:
                if key == "evidence_sources":
                    result[key] = []
                elif key == "should_call_emergency_now":
                    result[key] = False
                elif key == "routing_confidence":
                    result[key] = 40.0
                elif key in ["primary_phone", "primary_email", "primary_whatsapp"]:
                    result[key] = None
                else:
                    result[key] = "Unknown"
        return result
    except Exception as e:
        print(f"[Final Route] LLM failed: {e}")
        city = (location_context.get("city") or "").lower()
        issue = (hazard_context.get("issue_type") or "").lower()
        is_emerg = hazard_context.get("is_active_emergency", False)
        
        primary = "Local municipal authority"
        contact = "Rescue 1122" if is_emerg else "Rescue 1122 only if injury, trapped person, fire, or immediate danger"
        
        if "manhole" in issue or "sewage" in issue:
            if "lahore" in city:
                primary = "WASA Lahore"
            elif "karachi" in city:
                primary = "KWSC Karachi"
            elif "islamabad" in city:
                primary = "CDA Islamabad"
        elif "wire" in issue or "electric" in issue:
            if "lahore" in city:
                primary = "LESCO"
            elif "karachi" in city:
                primary = "K-Electric"
            elif "islamabad" in city:
                primary = "IESCO"
                
        return {
            "primary_authority": primary,
            "primary_department": "Operations & Complaints Division",
            "secondary_authority": "Rescue 1122" if is_emerg else "None",
            "emergency_contact": contact,
            "should_call_emergency_now": is_emerg,
            "routing_confidence": 35.0,
            "routing_reason": "No official source found. Fallback selected based on basic keyword matching.",
            "evidence_sources": [],
            "citizen_action": "Keep distance and report to utility helpline.",
            "authority_message_type": "complaint",
            "primary_phone": None,
            "primary_email": None,
            "primary_whatsapp": None
        }


def authority_discovery_agent(issue_type: str, description: str, location_text: str, gps: dict | None = None, image_summary: str = "") -> dict:
    """
    Orchestrates the full authority discovery workflow.
    """
    print(f"[Discovery Agent] Starting routing for: {issue_type} at {location_text}")
    # 1. Location extraction
    loc_ctx = extract_location_context(location_text, gps)
    print(f"[Discovery Agent] Extracted City: {loc_ctx.get('city')}, Jurisdiction: {loc_ctx.get('jurisdiction_hint')}")
    
    # 2. Hazard classification
    haz_ctx = classify_hazard(issue_type, description, image_summary)
    print(f"[Discovery Agent] Emergency Detected: {haz_ctx.get('is_active_emergency')}, Risk: {haz_ctx.get('risk_level')}")
    
    # 3. Build search queries
    queries = build_authority_search_queries(loc_ctx, haz_ctx)
    
    # 4. Discover candidates
    candidates = discover_authority_candidates(queries)
    print(f"[Discovery Agent] Found {len(candidates)} search candidates.")
    
    # 5. Rank candidates
    ranked = rank_authority_candidates(candidates, loc_ctx, haz_ctx)
    
    # 6. Final route
    route = final_authority_route(loc_ctx, haz_ctx, ranked)
    print(f"[Discovery Agent] Routed to primary: {route['primary_authority']}")
    
    # Double check contact details using regex on top candidates snippet
    snippets_blob = "\n\n".join(c["snippet"] for c in ranked[:5])
    regex_contacts = _extract_contact(snippets_blob)
    if not route.get("primary_phone"):
        route["primary_phone"] = regex_contacts.get("authority_phone")
    if not route.get("primary_email"):
        route["primary_email"] = regex_contacts.get("authority_email")
    if not route.get("primary_whatsapp"):
        route["primary_whatsapp"] = regex_contacts.get("authority_whatsapp")
        
    # Attach debug info
    route["_debug"] = {
        "location_context": loc_ctx,
        "hazard_context": haz_ctx,
        "search_queries": queries,
        "candidates_found_count": len(candidates)
    }
    
    return route


def dispatch_report(report: dict, location: str) -> dict:
    """
    Compatibility wrapper matching previous dispatcher interface.
    """
    full = report.get("full_report", {})
    incident_type = full.get("incident_type", "emergency")
    report_summary = report.get("report_summary", "")
    public_alert = report.get("public_alert_english", "")
    
    # Trigger full AI Discovery Agent
    route = authority_discovery_agent(
        issue_type=incident_type,
        description=report_summary,
        location_text=location,
        image_summary=full.get("scene_description", "")
    )
    
    # Construct compatibility dictionary matching old dispatch_report format
    whatsapp_number = route.get("primary_whatsapp")
    if whatsapp_number:
        whatsapp_number = "".join(ch for ch in str(whatsapp_number) if ch.isdigit())
        whatsapp_message = (
            f"🚨 ALERT - CrisisLens AI\n\n"
            f"Incident: {incident_type}\n"
            f"Risk Level: {full.get('risk_level', 'High')}\n"
            f"Location: {location}\n\n"
            f"{report_summary}\n\n"
            f"Please respond immediately."
        )
        encoded = urllib.parse.quote(whatsapp_message)
        whatsapp_link = f"https://wa.me/{whatsapp_number}?text={encoded}"
    else:
        whatsapp_link = None

    dispatch_data = {
        "authority_name": route["primary_authority"],
        "authority_phone": route.get("primary_phone") or route.get("emergency_contact", "1122"),
        "authority_whatsapp": whatsapp_number,
        "authority_email": route.get("primary_email"),
        "whatsapp_link": whatsapp_link,
        "dispatch_channel": "whatsapp" if whatsapp_number else ("email" if route.get("primary_email") else "call_only"),
        "search_confidence": int(route.get("routing_confidence", 50.0)),
        "source_found": route.get("routing_reason", "AI reasoning path"),
        "google_search_used": True,
        "google_search_succeeded": len(route.get("evidence_sources", [])) > 0,
        "google_search_queries": route["_debug"]["search_queries"][:2],
        "google_search_results_count": route["_debug"]["candidates_found_count"],
        "resolved_city": route["_debug"]["location_context"].get("city", "unknown"),
        "resolved_hazard_class": route["_debug"]["hazard_context"].get("issue_type", "unknown"),
        "routing_result": route # Attach full new routing result directly
    }
    
    # Try sending email
    email_sent = False
    sender = os.getenv("REPORT_EMAIL")
    password = os.getenv("REPORT_EMAIL_PASS")
    authority_email = dispatch_data.get("authority_email")
    if authority_email and sender and password:
        try:
            msg_email = MIMEMultipart()
            msg_email["From"] = sender
            msg_email["To"] = authority_email
            msg_email["Subject"] = f"[CrisisLens AI] Alert - {incident_type} at {location}"
            msg_email.attach(MIMEText(report_summary, "plain"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender, password)
                server.send_message(msg_email)
            email_sent = True
        except Exception as exc:
            print(f"[Dispatch] Email failed: {exc}")
            
    dispatch_data["email_sent"] = email_sent
    dispatch_data["email_attempted"] = bool(authority_email)
    
    return dispatch_data


def _resolve_authority(location: str, incident_type: str, signal_text: str) -> dict:
    """
    Backward compatibility helper mapping to authority_discovery_agent.
    """
    try:
        route = authority_discovery_agent(
            issue_type=incident_type,
            description=signal_text,
            location_text=location
        )
        return {
            "authority": route["primary_authority"],
            "phone": route.get("primary_phone") or route.get("emergency_contact", "1122"),
            "city": route["_debug"]["location_context"].get("city", "unknown"),
            "hazard_class": route["_debug"]["hazard_context"].get("issue_type", "unknown"),
            "is_generic": route.get("routing_confidence", 100.0) < 60.0,
            "routing_result": route,
        }
    except Exception as e:
        print(f"[Resolve Authority Fallback] Error: {e}")
        return {
            "authority": "Local municipal authority",
            "phone": None,
            "city": "unknown",
            "hazard_class": incident_type,
            "is_generic": True
        }
