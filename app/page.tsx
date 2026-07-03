"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node
} from "@xyflow/react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Boxes,
  Braces,
  Cable,
  Database,
  GitBranch,
  Loader2,
  Play,
  RotateCcw,
  ServerCog,
  Sparkles
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type DesignNode = {
  id: string;
  label: string;
  type?: string;
  description?: string;
};

type DesignEdge = {
  id?: string;
  source: string;
  target: string;
  label?: string;
};

type SystemDesign = {
  nodes: DesignNode[];
  edges: DesignEdge[];
  services: string[];
  databases: string[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ✅ FIXED: Removed Uber example, added clean prompts
const samplePrompts = [
  "Design a payment processing platform like Stripe with real-time fraud detection, webhook notifications, and multi-currency support.",
  "Design a video streaming platform like Netflix with content catalog, personalized recommendations, user profiles, and viewing analytics.",
  "Design a ride-hailing platform like Uber with real-time matching, location tracking, surge pricing, and payment processing.",
  "Design a social media platform like Twitter with tweets, follows, timelines, search, and trending topics.",
  "Design an e-commerce platform like Amazon with product catalog, shopping cart, order processing, and recommendations.",
];

const initialDesign: SystemDesign = {
  nodes: [
    {
      id: "client",
      label: "User Apps",
      type: "client",
      description: "Web and mobile entry points"
    },
    {
      id: "gateway",
      label: "API Gateway",
      type: "gateway",
      description: "Routing, auth, throttling"
    },
    {
      id: "service-core",
      label: "Core Service",
      type: "service",
      description: "Primary domain workflow"
    },
    {
      id: "events",
      label: "Event Bus",
      type: "queue",
      description: "Async orchestration"
    },
    {
      id: "database",
      label: "Primary Database",
      type: "database",
      description: "Durable system records"
    }
  ],
  edges: [
    { source: "client", target: "gateway", label: "requests" },
    { source: "gateway", target: "service-core", label: "routes" },
    { source: "service-core", target: "events", label: "publishes" },
    { source: "service-core", target: "database", label: "persists" }
  ],
  services: ["API Gateway", "Core Service", "Event Bus"],
  databases: ["Primary Database"]
};

const nodePalette: Record<string, { color: string; bg: string; icon: string }> = {
  client: { color: "#1d4ed8", bg: "#eff6ff", icon: "UX" },
  gateway: { color: "#6d28d9", bg: "#f5f3ff", icon: "GW" },
  service: { color: "#0f766e", bg: "#ecfdf5", icon: "SV" },
  database: { color: "#b45309", bg: "#fffbeb", icon: "DB" },
  queue: { color: "#be123c", bg: "#fff1f2", icon: "EV" },
  cache: { color: "#047857", bg: "#ecfdf5", icon: "CA" },
  storage: { color: "#0369a1", bg: "#f0f9ff", icon: "ST" },
  external: { color: "#475569", bg: "#f8fafc", icon: "EX" }
};

function getNodeStyle(type = "service") {
  const palette = nodePalette[type] ?? nodePalette.service;
  return {
    border: `1px solid ${palette.color}33`,
    borderLeft: `5px solid ${palette.color}`,
    background: palette.bg,
    color: "#172033",
    borderRadius: 8,
    width: 210,
    minHeight: 82,
    boxShadow: "0 18px 48px rgba(31, 41, 55, 0.12)"
  };
}

function layoutNodes(design: SystemDesign): Node[] {
  const columns = Math.max(1, Math.ceil(Math.sqrt(design.nodes.length)));
  return design.nodes.map((item, index) => {
    const row = Math.floor(index / columns);
    const col = index % columns;
    const palette = nodePalette[item.type ?? "service"] ?? nodePalette.service;

    return {
      id: item.id,
      type: "default",
      position: {
        x: col * 290 + (row % 2 ? 80 : 0),
        y: row * 170
      },
      data: {
        label: (
          <div className="arch-node">
            <span style={{ color: palette.color, background: "#ffffff" }}>
              {palette.icon}
            </span>
            <div>
              <strong>{item.label}</strong>
              <small>{item.description || item.type || "architecture component"}</small>
            </div>
          </div>
        )
      },
      style: getNodeStyle(item.type)
    };
  });
}

function layoutEdges(design: SystemDesign): Edge[] {
  return design.edges.map((edge, index) => ({
    id: edge.id ?? `${edge.source}-${edge.target}-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.label,
    animated: true,
    style: { stroke: "#64748b", strokeWidth: 2 },
    labelStyle: { fill: "#334155", fontWeight: 600 },
    labelBgStyle: { fill: "#ffffff", fillOpacity: 0.88 }
  }));
}

export default function Home() {
  // ✅ FIXED: Start with empty prompt
  const [prompt, setPrompt] = useState("");
  const [design, setDesign] = useState<SystemDesign>(initialDesign);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes(initialDesign));
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges(initialDesign));

  useEffect(() => {
    setNodes(layoutNodes(design));
    setEdges(layoutEdges(design));
  }, [design, setEdges, setNodes]);

  const stats = useMemo(
    () => [
      { label: "Components", value: design.nodes.length, icon: Boxes },
      { label: "Connections", value: design.edges.length, icon: Cable },
      { label: "Services", value: design.services.length, icon: ServerCog },
      { label: "Databases", value: design.databases.length, icon: Database }
    ],
    [design]
  );

  const generateArchitecture = useCallback(
    async (event?: FormEvent) => {
      event?.preventDefault();
      setLoading(true);
      setError("");

      try {
        const response = await fetch(`${API_URL}/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt })
        });

        if (!response.ok) {
          throw new Error(`FastAPI returned ${response.status}`);
        }

        const result = (await response.json()) as SystemDesign;
        setDesign(result);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to generate architecture. Is FastAPI running on port 8000?"
        );
      } finally {
        setLoading(false);
      }
    },
    [prompt]
  );

  return (
    <main className="page-shell">
      <section className="topbar">
        <div className="brand-mark">
          <GitBranch size={22} />
        </div>
        <div>
          <strong>ArchFlow AI</strong>
          <span>System design visualization studio</span>
        </div>
      </section>

      <section className="workspace">
        <motion.aside
          className="control-panel"
          initial={{ opacity: 0, x: -24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
        >
          <div className="panel-kicker">
            <Sparkles size={16} />
            AI-powered architecture generator
          </div>
          <h1>Turn product ideas into system maps.</h1>
          <p>
            Describe the platform. ArchFlow asks the FastAPI model service for
            structured JSON, then renders the workflow as an interactive diagram.
          </p>

          <form onSubmit={generateArchitecture} className="prompt-form">
            <label htmlFor="prompt">Architecture prompt</label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={7}
              placeholder="Design a [platform] with [features]..."
            />
            <div className="button-row">
              <button className="btn primary-action" disabled={loading || !prompt.trim()}>
                {loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
                Generate flow
              </button>
              <button
                type="button"
                className="btn ghost-action"
                onClick={() => setDesign(initialDesign)}
              >
                <RotateCcw size={18} />
              </button>
            </div>
          </form>

          <div className="samples">
            <small style={{ color: "#64748b", fontWeight: 600, marginBottom: 4 }}>
              Try these examples:
            </small>
            {samplePrompts.map((item) => (
              <button key={item} type="button" onClick={() => setPrompt(item)}>
                {item}
                <ArrowRight size={14} />
              </button>
            ))}
          </div>

          <AnimatePresence>
            {error && (
              <motion.div
                className="error-box"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.aside>

        <section className="canvas-stage">
          <motion.div
            className="metrics-strip"
            initial={{ opacity: 0, y: -14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.1 }}
          >
            {stats.map((stat) => {
              const Icon = stat.icon;
              return (
                <div key={stat.label}>
                  <Icon size={18} />
                  <span>{stat.label}</span>
                  <strong>{stat.value}</strong>
                </div>
              );
            })}
          </motion.div>

          <motion.div
            className="diagram-shell"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.65, ease: "easeOut" }}
          >
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              fitView
              fitViewOptions={{ padding: 0.2 }}
            >
              <Background
                color="#cbd5e1"
                gap={22}
                size={1.4}
                variant={BackgroundVariant.Dots}
              />
              <Controls position="bottom-right" />
              <MiniMap
                position="bottom-left"
                pannable
                zoomable
                nodeColor={(node) => {
                  const type = design.nodes.find((item) => item.id === node.id)?.type;
                  return (nodePalette[type ?? "service"] ?? nodePalette.service).color;
                }}
              />
            </ReactFlow>
          </motion.div>
        </section>
      </section>

      <section className="json-dock">
        <div>
          <Braces size={18} />
          Structured output
        </div>
        <pre>{JSON.stringify(design, null, 2)}</pre>
      </section>
    </main>
  );
}