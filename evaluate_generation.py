import re
import math

# Define a set of mock scenarios representing typical user requests
# and the generated outputs from different generator versions.
SCENARIOS = [
    {
        "id": "scenario_01",
        "description": "Arctic Survival training with limited equipment",
        "requirements": ["Construct snow shelter", "Perform buddy checks for frostbite"],
        "allowed_locations": ["Kiruna"],
        "allowed_materials": ["sleeping bag", "snow shovel"],
        "retrieved_context": [
            "arctic_survival.txt: Structural thickness of snow ceilings must remain at a minimum of 30 centimeters for safety.",
            "arctic_survival.txt: Safety check: buddy check for white spots (early frostbite) every 20 minutes.",
            "arctic_survival.txt: Treat patients utilizing field sleeping bag warming configurations."
        ],
        "outputs": {
            "generator_v1_good": (
                "Exercise Plan: Arctic Winter Ops. Location: Kiruna. "
                "Trainees will construct a snow shelter (Quinzhee) ensuring a minimum snow ceiling thickness of 30 centimeters. "
                "Every 20 minutes, buddy checks must be performed to inspect for white spots indicating frostbite. "
                "Each group will carry a sleeping bag and a snow shovel to assist in construction and safety drills."
            ),
            "generator_v1_hallucinated": (
                "Exercise Plan: Winter Storm. Location: Kiruna. "
                "Trainees will build a snow cave. Because it is extremely cold, each squad will carry a propane heater stove "
                "and use GPS tracker beacons. No buddy check guidelines are provided."
            )
        }
    },
    {
        "id": "scenario_02",
        "description": "Anti-Armor defense setup with interlocking fields of fire",
        "requirements": ["ARMOR protocol", "overlapping fields of fire at 45 degrees"],
        "allowed_locations": ["Eksjö"],
        "allowed_materials": ["NLAW", "radio"],
        "retrieved_context": [
            "iron_wall.txt: Cover the critical rules of anti-armor engagements (ARMOR).",
            "iron_wall.txt: Keep weapon fields of fire overlapping at an angle of exactly 45 degrees.",
            "iron_wall.txt: Ensure NLAW launchers are deployed in covered positions with clear backblast zones."
        ],
        "outputs": {
            "generator_v1_good": (
                "Tactical Drill: Iron Shield at Eksjö training field. "
                "The platoon will implement the ARMOR protocol to consolidate defenses. "
                "NLAW operators will position their weapons in covered sites. "
                "To maximize effectiveness, ensure overlapping fields of fire at 45 degrees. "
                "Communicate coordinates using analog tactical radio."
            ),
            "generator_v1_bad_location": (
                "Tactical Drill: Iron Shield. Location: Revingehed. "
                "The platoon will set up defenses using NLAW launchers. "
                "Ensure fields of fire overlap at a 45 degree angle."
            )
        }
    }
]

def calculate_faithfulness(generated_text: str, retrieved_contexts: list[str]) -> float:
    """
    Calculates the faithfulness score (fraction of generated content words
    supported by the retrieved source context), excluding standard stopwords.
    """
    gen_words = set(re.findall(r'\b\w{4,}\b', generated_text.lower()))
    ctx_words = set(re.findall(r'\b\w{4,}\b', " ".join(retrieved_contexts).lower()))
    
    if not gen_words:
        return 1.0
        
    stopwords = {"with", "that", "this", "from", "they", "will", "your", "have", "been", "location", "exercise", "plan", "drill"}
    gen_content_words = gen_words - stopwords
    ctx_content_words = ctx_words - stopwords
    
    if not gen_content_words:
        return 1.0
        
    overlap = gen_content_words.intersection(ctx_content_words)
    return len(overlap) / len(gen_content_words)

def calculate_requirement_adherence(generated_text: str, requirements: list[str]) -> float:
    """
    Checks if all required topics, learning outcomes, or protocols
    are present in the generated output text.
    """
    if not requirements:
        return 1.0
        
    hits = 0
    text_lower = generated_text.lower()
    for req in requirements:
        # Check if all major words of the requirement are in the text
        req_words = re.findall(r'\b\w{3,}\b', req.lower())
        if all(w in text_lower for w in req_words):
            hits += 1
    return hits / len(requirements)

def calculate_constraint_adherence(generated_text: str, allowed_locations: list[str], allowed_materials: list[str]) -> tuple[float, list[str]]:
    """
    Checks if the generated text mentions any locations or materials that are
    NOT allowed, flagging hallucinations.
    Returns the adherence score [0.0, 1.0] and a list of violation messages.
    """
    violations = []
    text_lower = generated_text.lower()
    
    # Reference lists of all known locations and materials in the domain
    all_known_locations = ["kiruna", "revingehed", "eksjö", "berga", "utö", "korsholmen", "marnö", "söderby", "käringberget"]
    all_known_materials = ["sleeping bag", "snow shovel", "stove", "tent", "nlaw", "rbs 56", "radio", "ra 1570", "gps tracker", "heater stove", "propane heater", "tourniquet", "life jacket", "flytväst"]
    
    # Check locations
    allowed_locs_lower = [loc.lower() for loc in allowed_locations]
    for loc in all_known_locations:
        if loc in text_lower:
            if loc not in allowed_locs_lower:
                violations.append(f"Location Violation: '{loc.capitalize()}' used, but only {allowed_locations} are allowed.")
                
    # Check materials
    allowed_mats_lower = [mat.lower() for mat in allowed_materials]
    for mat in all_known_materials:
        # Simple phrase match
        if mat in text_lower:
            if mat not in allowed_mats_lower:
                # Special check to avoid sub-phrase matches if they overlap
                violations.append(f"Material Violation: '{mat}' used, but only {allowed_materials} are allowed.")
                
    total_checks = len(violations)
    if total_checks == 0:
        return 1.0, []
        
    # We penalize based on number of violations
    score = max(0.0, 1.0 - (total_checks * 0.5))
    return score, violations

def main():
    print("="*80)
    print("                   RAG GENERATION EVALUATION REPORT")
    print("="*80)
    
    for scenario in SCENARIOS:
        print(f"\nScenario: {scenario['description']}")
        print(f"  Requirements:  {scenario['requirements']}")
        print(f"  Allowed Locs:  {scenario['allowed_locations']}")
        print(f"  Allowed Mats:  {scenario['allowed_materials']}")
        print("-"*80)
        
        for gen_name, output_text in scenario["outputs"].items():
            print(f"  Evaluated Model Output: [{gen_name}]")
            print(f"  Generated Text: \"{output_text}\"")
            
            # Run evaluations
            faithfulness = calculate_faithfulness(output_text, scenario["retrieved_context"])
            req_adherence = calculate_requirement_adherence(output_text, scenario["requirements"])
            constraint_score, violations = calculate_constraint_adherence(
                output_text, 
                scenario["allowed_locations"], 
                scenario["allowed_materials"]
            )
            
            print(f"  Metrics:")
            print(f"    - Faithfulness Score:          {faithfulness*100:>5.1f}%")
            print(f"    - Requirement Adherence:       {req_adherence*100:>5.1f}%")
            print(f"    - Constraint Adherence:        {constraint_score*100:>5.1f}%")
            
            if violations:
                print("    - Violations Found:")
                for v in violations:
                    print(f"        * {v}")
            else:
                print("    - Violations Found:            None (Passed)")
            print("-"*50)
            
    print("="*80)
    print("[OK] Generation evaluation simulation completed.")

if __name__ == "__main__":
    main()
