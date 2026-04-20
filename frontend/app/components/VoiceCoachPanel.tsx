"use client";

import { useMemo, useRef, useState } from "react";
import { appCoach } from "../lib/api";

declare global {
  interface Window {
    webkitSpeechRecognition?: any;
    SpeechRecognition?: any;
  }
}

interface Props {
  tab: string;
  appGoal: string;
  context: Record<string, unknown>;
}

export default function VoiceCoachPanel({ tab, appGoal, context }: Props) {
  const [open, setOpen] = useState(false);
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [actions, setActions] = useState<string[]>([]);
  const [priority, setPriority] = useState<string>("next");
  const [model, setModel] = useState<string>("");
  const [error, setError] = useState<string>("");

  const recognitionRef = useRef<any>(null);

  const speechSupported = useMemo(
    () => typeof window !== "undefined" && (!!window.SpeechRecognition || !!window.webkitSpeechRecognition),
    []
  );

  const startListening = () => {
    if (!speechSupported || listening) return;

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recog = new SR();
    recognitionRef.current = recog;
    recog.lang = "en-US";
    recog.interimResults = true;
    recog.continuous = false;

    let finalText = "";

    recog.onstart = () => {
      setError("");
      setListening(true);
      setTranscript("");
    };

    recog.onresult = (event: any) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const txt = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += txt;
        else interim += txt;
      }
      setTranscript((finalText + " " + interim).trim());
    };

    recog.onerror = (event: any) => {
      setListening(false);
      setError(`Mic error: ${event?.error || "unknown"}`);
    };

    recog.onend = () => {
      setListening(false);
      if (finalText.trim()) {
        setTranscript(finalText.trim());
      }
    };

    recog.start();
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setListening(false);
  };

  const speak = (text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window) || !text.trim()) return;
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.02;
    utter.pitch = 1.0;
    utter.volume = 1.0;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  };

  const askCoach = async () => {
    if (!transcript.trim()) return;
    setThinking(true);
    setError("");
    try {
      const res = await appCoach({
        tab,
        user_message: transcript.trim(),
        app_goal: appGoal,
        context,
      });
      setReply(res.reply || "");
      setActions(res.next_actions || []);
      setPriority(res.priority || "next");
      setModel(res.model || "");
      speak(res.reply || "");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Coach failed");
    } finally {
      setThinking(false);
    }
  };

  return (
    <div className="fixed bottom-5 right-5 z-50">
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="px-4 py-2 rounded-full border border-cyan-400/40 text-cyan-200 bg-cyan-500/20 shadow-[0_0_24px_rgba(34,211,238,0.35)] hover:bg-cyan-500/30 transition-all"
          title="Open Voice Coach"
        >
          Voice Coach
        </button>
      )}

      {open && (
        <div className="w-[360px] max-w-[92vw] bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-cyan-200">Empire Voice Coach</div>
              <div className="text-[11px] text-zinc-500">Section: {tab}</div>
            </div>
            <button onClick={() => setOpen(false)} className="text-zinc-500 hover:text-zinc-300 text-sm">✕</button>
          </div>

          <div className="flex gap-2">
            <button
              onClick={listening ? stopListening : startListening}
              disabled={!speechSupported || thinking}
              className="px-3 py-2 rounded-lg text-xs font-semibold bg-zinc-800 border border-zinc-700 hover:bg-zinc-700 disabled:opacity-40"
            >
              {listening ? "Stop Mic" : "Start Mic"}
            </button>
            <button
              onClick={askCoach}
              disabled={thinking || !transcript.trim()}
              className="flex-1 px-3 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-700 hover:to-blue-700 disabled:opacity-40"
            >
              {thinking ? "Thinking..." : "Get Suggestion"}
            </button>
          </div>

          {!speechSupported && <div className="text-[11px] text-amber-400">Speech recognition not supported in this browser.</div>}

          <textarea
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder="Ask what to do next in this section..."
            className="w-full min-h-[80px] p-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm placeholder-zinc-500 focus:border-cyan-500 focus:outline-none"
          />

          {error && <div className="text-[11px] text-red-400">{error}</div>}

          {reply && (
            <div className="border border-zinc-700 rounded-lg p-3 bg-zinc-800/60 space-y-2">
              <div className="text-[11px] text-zinc-400">Priority: {priority}</div>
              <div className="text-sm text-zinc-200">{reply}</div>
              {actions.length > 0 && (
                <ul className="text-xs text-zinc-300 list-disc pl-4 space-y-1">
                  {actions.map((a, i) => <li key={i}>{a}</li>)}
                </ul>
              )}
              {model && <div className="text-[10px] text-zinc-500">Model: {model}</div>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
