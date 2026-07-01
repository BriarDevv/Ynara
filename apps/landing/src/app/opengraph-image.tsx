import { ImageResponse } from "next/og";
import { site } from "@/content/ynara";

export const alt = "Ynara · Tu asistente personal con memoria";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    <div
      style={{
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "radial-gradient(60% 55% at 50% 38%, #1a2440 0%, #0a0c12 70%)",
        color: "#f3f0ea",
        fontFamily: "sans-serif",
      }}
    >
      {/* Diamante de presencia (nod al mark) */}
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 14,
          background: "linear-gradient(135deg, #8265a3, #2f5aa6)",
          transform: "rotate(45deg)",
          marginBottom: 44,
          boxShadow: "0 0 80px 10px rgba(75,126,230,0.45)",
        }}
      />
      <div
        style={{
          fontSize: 140,
          fontWeight: 700,
          letterSpacing: "-0.04em",
          lineHeight: 1,
        }}
      >
        Ynara
      </div>
      <div style={{ display: "flex", marginTop: 8, fontSize: 30, color: "#8b9ad0" }}>
        Organiza · Recuerda · Acompaña
      </div>
      <div
        style={{
          display: "flex",
          marginTop: 40,
          fontSize: 36,
          color: "#f3f0ea",
          maxWidth: 760,
          textAlign: "center",
        }}
      >
        {site.tagline}
      </div>
    </div>,
    size,
  );
}
