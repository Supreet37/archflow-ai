from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# KEEP SMALL - CPU friendly!
MODEL_NAME = "google/flan-t5-small"  # Only 308MB

class ArchitectureRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=4000)
    use_model: bool = True

class ArchitectureNode(BaseModel):
    id: str
    label: str
    type: str = "service"
    description: str = ""

class ArchitectureEdge(BaseModel):
    source: str
    target: str
    label: str = "connects"

class ArchitectureDesign(BaseModel):
    nodes: list[ArchitectureNode]
    edges: list[ArchitectureEdge]
    services: list[str]
    databases: list[str]

app = FastAPI(title="ArchFlow AI API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@lru_cache(maxsize=1)
def get_model_pipeline():
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
    
    print("Loading model (only 308MB)...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    print("Model ready!")
    
    return pipeline(
        "text2text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=500,  # More output for better understanding
        do_sample=False,
    )

def architecture_instruction(prompt: str) -> str:
    """SMARTER prompt for small model"""
    return f"""Design a complete microservices system for: {prompt}

Think about:
- What services are needed? List 4-8 services
- What databases are needed?
- How do services connect?

IMPORTANT: Return ONLY valid JSON with this exact structure:
{{
  "services": [
    {{"name": "service1", "description": "what it does"}},
    {{"name": "service2", "description": "what it does"}}
  ],
  "databases": ["db1", "db2"],
  "connections": [
    {{"from": "service1", "to": "service2", "purpose": "why"}}
  ]
}}

Example for a ride-sharing app:
{{
  "services": [
    {{"name": "Matching Service", "description": "Match riders with drivers"}},
    {{"name": "Location Service", "description": "Track real-time locations"}},
    {{"name": "Payment Service", "description": "Process payments"}}
  ],
  "databases": ["Trips", "Users"],
  "connections": [
    {{"from": "Matching Service", "to": "Location Service", "purpose": "get nearby drivers"}}
  ]
}}

Now generate for: {prompt}

JSON:"""

def generate_model_text(prompt: str) -> str:
    generator = get_model_pipeline()
    result = generator(architecture_instruction(prompt))[0]["generated_text"]
    print(f"AI Output: {result[:200]}...")
    return result

def extract_json(text: str) -> dict[str, Any] | None:
    """Extract JSON from AI response"""
    # Try multiple patterns
    patterns = [
        r'\{[^{}]*"services"[^{}]*\}[^{}]*\}',  # Nested JSON
        r'\{.*"services".*\}',  # Any JSON with services
        r'\{.*\}',  # Any JSON
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            candidate = match.group(0)
            try:
                # Fix common issues
                candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
                candidate = re.sub(r'(?<!")(\b\w+\b)(?=":)', r'"\1"', candidate)
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and parsed.get("services"):
                    return parsed
            except:
                continue
    return None

def create_architecture_from_ai(ai_data: dict, prompt: str) -> ArchitectureDesign:
    """Convert AI output to architecture design"""
    
    # Always start with these
    nodes = [
        ArchitectureNode(
            id="client",
            label="Client App",
            type="client",
            description="User interface"
        ),
        ArchitectureNode(
            id="gateway",
            label="API Gateway",
            type="gateway",
            description="Single entry point"
        ),
    ]
    
    service_id_map = {}
    
    # Add services from AI
    for service in ai_data.get("services", []):
        if isinstance(service, dict):
            name = service.get("name", "").strip()
            desc = service.get("description", f"{name} service")
            if name:
                node_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
                nodes.append(ArchitectureNode(
                    id=node_id,
                    label=name,
                    type="service",
                    description=desc[:120]
                ))
                service_id_map[name.lower()] = node_id
    
    # Add databases
    for db in ai_data.get("databases", []):
        if isinstance(db, str):
            db_name = db.strip()
            if db_name:
                node_id = re.sub(r'[^a-z0-9]+', '-', db_name.lower()).strip('-')
                nodes.append(ArchitectureNode(
                    id=node_id,
                    label=db_name,
                    type="database",
                    description=f"{db_name} database"
                ))
    
    # Ensure we have at least one database
    if not any(n.type == "database" for n in nodes):
        nodes.append(ArchitectureNode(
            id="primary-db",
            label="Primary Database",
            type="database",
            description="Main data storage"
        ))
    
    # Build edges
    edges = []
    
    # Client to Gateway
    edges.append(ArchitectureEdge(
        source="client",
        target="gateway",
        label="HTTPS"
    ))
    
    # AI connections
    for conn in ai_data.get("connections", []):
        if isinstance(conn, dict):
            from_svc = conn.get("from", "").strip().lower()
            to_svc = conn.get("to", "").strip().lower()
            purpose = conn.get("purpose", "connects")
            
            from_id = service_id_map.get(from_svc)
            to_id = service_id_map.get(to_svc)
            
            if from_id and to_id and from_id != to_id:
                edges.append(ArchitectureEdge(
                    source=from_id,
                    target=to_id,
                    label=purpose[:48]
                ))
    
    # Auto-connect remaining services to gateway
    service_nodes = [n for n in nodes if n.type == "service"]
    for service in service_nodes[:4]:  # Limit to 4
        if not any(e.source == "gateway" and e.target == service.id for e in edges):
            edges.append(ArchitectureEdge(
                source="gateway",
                target=service.id,
                label="routes"
            ))
    
    # Connect services to database
    data_nodes = [n for n in nodes if n.type == "database"]
    if data_nodes and service_nodes:
        for service in service_nodes[:3]:
            edges.append(ArchitectureEdge(
                source=service.id,
                target=data_nodes[0].id,
                label="persists"
            ))
    
    return ArchitectureDesign(
        nodes=nodes,
        edges=dedupe_edges(edges),
        services=[n.label for n in nodes if n.type in ["gateway", "service"]],
        databases=[n.label for n in nodes if n.type == "database"],
    )

def dedupe_edges(edges: list[ArchitectureEdge]) -> list[ArchitectureEdge]:
    seen = set()
    result = []
    for edge in edges:
        key = (edge.source, edge.target, edge.label)
        if key not in seen:
            seen.add(key)
            result.append(edge)
    return result

def fallback_design(prompt: str) -> ArchitectureDesign:
    """Smart fallback when AI fails"""
    prompt_lower = prompt.lower()
    
    # Smart domain detection
    domains = {
        "ride|uber|driver|passenger|trip|location|matching": [
            ("Matching Service", "Match users with services"),
            ("Location Service", "Track real-time locations"),
            ("Trip Service", "Manage trips"),
            ("Payment Service", "Process payments"),
            ("Notification Service", "Send notifications"),
        ],
        "salon|appointment|stylist|booking|beauty|spa|barber|saloon": [
            ("Appointment Service", "Manage bookings and schedules"),
            ("Stylist Service", "Manage stylists/professionals"),
            ("Client Service", "Manage customer profiles"),
            ("Payment Service", "Process payments"),
            ("Notification Service", "Send appointment reminders"),
            ("Service Catalog", "Manage available services"),
        ],
        "ecommerce|shop|store|product|cart|order|inventory": [
            ("Product Service", "Manage product catalog"),
            ("Cart Service", "Manage shopping carts"),
            ("Order Service", "Process orders"),
            ("Payment Service", "Process payments"),
            ("Inventory Service", "Track inventory"),
            ("Shipping Service", "Manage deliveries"),
        ],
        "streaming|video|movie|content|watch|netflix": [
            ("Content Service", "Manage content catalog"),
            ("Recommendation Service", "Personalized recommendations"),
            ("Streaming Service", "Deliver content"),
            ("User Service", "Manage user profiles"),
            ("Analytics Service", "Track viewing patterns"),
        ],
        "delivery|food|restaurant|kitchen": [
            ("Restaurant Service", "Manage restaurants"),
            ("Order Service", "Process orders"),
            ("Delivery Service", "Manage deliveries"),
            ("Payment Service", "Process payments"),
            ("Notification Service", "Send updates"),
        ],
        "healthcare|doctor|patient|clinic|hospital|medical": [
            ("Patient Service", "Manage patient records"),
            ("Appointment Service", "Schedule appointments"),
            ("Billing Service", "Process billing"),
            ("Notification Service", "Send reminders"),
            ("Medical Records", "Store medical data"),
        ],
        "banking|finance|payment|transaction|account|wallet": [
            ("Account Service", "Manage accounts"),
            ("Transaction Service", "Process transactions"),
            ("Payment Service", "Process payments"),
            ("Notification Service", "Send alerts"),
            ("Fraud Detection", "Detect suspicious activity"),
        ],
        "social|post|feed|follow|like|comment|messaging": [
            ("Feed Service", "Generate feeds"),
            ("Post Service", "Manage posts"),
            ("User Service", "Manage users"),
            ("Notification Service", "Send notifications"),
            ("Messaging Service", "Handle messages"),
        ],
        "education|learning|course|student|teacher|class": [
            ("Course Service", "Manage courses"),
            ("Student Service", "Manage students"),
            ("Enrollment Service", "Manage enrollments"),
            ("Assessment Service", "Handle assessments"),
            ("Notification Service", "Send updates"),
        ],
        "realestate|property|rent|buy|sell|house": [
            ("Property Service", "Manage properties"),
            ("Listing Service", "Manage listings"),
            ("User Service", "Manage users"),
            ("Payment Service", "Process payments"),
            ("Notification Service", "Send updates"),
        ],
        "event|ticket|concert|booking|venue": [
            ("Event Service", "Manage events"),
            ("Ticket Service", "Manage tickets"),
            ("User Service", "Manage users"),
            ("Payment Service", "Process payments"),
            ("Notification Service", "Send updates"),
        ],
        "travel|hotel|flight|booking|reservation": [
            ("Hotel Service", "Manage hotels"),
            ("Flight Service", "Manage flights"),
            ("Booking Service", "Manage bookings"),
            ("Payment Service", "Process payments"),
            ("Notification Service", "Send updates"),
        ],
    }
    
    service_list = []
    for pattern, services in domains.items():
        if any(keyword in prompt_lower for keyword in pattern.split("|")):
            service_list.extend(services)
            break
    
    # Generic if no domain matched
    if not service_list:
        # Extract potential services from prompt
        words = prompt_lower.split()
        service_list = []
        
        # Try to find service names from prompt
        common_services = {
            "order": ("Order Service", "Process orders"),
            "payment": ("Payment Service", "Process payments"),
            "user": ("User Service", "Manage users"),
            "notification": ("Notification Service", "Send notifications"),
            "analytics": ("Analytics Service", "Analyze data"),
            "search": ("Search Service", "Enable search"),
            "report": ("Reporting Service", "Generate reports"),
            "auth": ("Auth Service", "Handle authentication"),
        }
        
        for word, service in common_services.items():
            if word in prompt_lower:
                service_list.append(service)
        
        # Still nothing? Add generic
        if not service_list:
            service_list = [
                ("Core Service", "Core business logic"),
                ("Workflow Service", "Orchestrate workflows"),
            ]
    
    # Build nodes
    nodes = [
        ArchitectureNode(id="client", label="Client App", type="client", description="User interface"),
        ArchitectureNode(id="gateway", label="API Gateway", type="gateway", description="Single entry point"),
    ]
    
    for label, desc in service_list[:6]:  # Max 6 services
        node_id = re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')
        nodes.append(ArchitectureNode(
            id=node_id,
            label=label,
            type="service",
            description=desc
        ))
    
    # Add database and cache
    nodes.extend([
        ArchitectureNode(
            id="primary-db",
            label="Primary Database",
            type="database",
            description="Main data storage"
        ),
        ArchitectureNode(
            id="cache",
            label="Cache Layer",
            type="cache",
            description="High-speed cache"
        ),
    ])
    
    # Add event bus if realtime needed
    if any(w in prompt_lower for w in ["realtime", "event", "notification", "async", "message", "live"]):
        nodes.append(ArchitectureNode(
            id="event-bus",
            label="Event Bus",
            type="queue",
            description="Async event distribution"
        ))
    
    # Add storage if files needed
    if any(w in prompt_lower for w in ["file", "image", "video", "document", "media", "upload"]):
        nodes.append(ArchitectureNode(
            id="storage",
            label="Object Storage",
            type="storage",
            description="Binary file storage"
        ))
    
    # Build edges
    edges = []
    service_ids = [n.id for n in nodes if n.type == "service"]
    
    # Gateway to services
    for service in service_ids[:4]:
        edges.append(ArchitectureEdge(source="gateway", target=service, label="routes"))
    
    # Services to database
    if service_ids:
        for service in service_ids[:3]:
            edges.append(ArchitectureEdge(source=service, target="primary-db", label="persists"))
    
    # Client to gateway
    edges.append(ArchitectureEdge(source="client", target="gateway", label="HTTPS"))
    
    # Cache
    edges.append(ArchitectureEdge(source="primary-db", target="cache", label="caches"))
    
    return ArchitectureDesign(
        nodes=nodes,
        edges=dedupe_edges(edges),
        services=[n.label for n in nodes if n.type in ["gateway", "service", "queue"]],
        databases=[n.label for n in nodes if n.type in ["database", "cache", "storage"]],
    )

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": MODEL_NAME}

@app.post("/generate", response_model=ArchitectureDesign)
def generate_architecture(request: ArchitectureRequest) -> ArchitectureDesign:
    if not request.use_model:
        return fallback_design(request.prompt)
    
    try:
        output = generate_model_text(request.prompt)
        parsed = extract_json(output)
        if parsed and parsed.get("services"):
            return create_architecture_from_ai(parsed, request.prompt)
    except Exception as e:
        print(f"AI failed: {e}")
    
    return fallback_design(request.prompt)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)