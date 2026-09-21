/** Wireframe 3 — Scan intro. Phase 2 — live. Requests camera permission to
 * reflect real permission/resolution state in the status tag (specs.md §2:
 * "Camera ready · 720p" status tag reflecting real permission/resolution
 * state"); Proceed is disabled until permission is granted. */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Cta, IconBtn, Item, Meta, Note, Tag, Top } from "../components/Primitives";

type PermissionState = "checking" | "granted" | "denied";

export default function Screen3ScanIntro() {
  const navigate = useNavigate();
  const [permission, setPermission] = useState<PermissionState>("checking");
  const [resolution, setResolution] = useState<string>("720p");

  useEffect(() => {
    let cancelled = false;

    navigator.mediaDevices
      .getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } } })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        const track = stream.getVideoTracks()[0];
        const settings = track?.getSettings();
        if (settings?.height) {
          setResolution(settings.height >= 720 ? "720p" : `${settings.height}p`);
        }
        stream.getTracks().forEach((t) => t.stop());
        setPermission("granted");
      })
      .catch(() => {
        if (!cancelled) setPermission("denied");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <Top>
        <IconBtn onClick={() => navigate(-1)}>‹</IconBtn>
        <Tag variant={permission === "granted" ? "accent" : permission === "denied" ? "bad" : "mute"}>
          {permission === "checking" && "Checking camera…"}
          {permission === "granted" && `Camera ready · ${resolution}`}
          {permission === "denied" && "Camera permission denied"}
        </Tag>
      </Top>
      <Card className="h-[170px] flex items-center justify-center bg-accent-soft border-accent-dim">
        <span className="text-5xl">📷</span>
      </Card>
      <h2 className="text-[26px] font-bold text-center mb-1.5">Before we begin</h2>
      <p className="text-sm text-text-2 text-center mb-5">Position the device at eye level and follow these guidelines.</p>
      <Card><Item><Meta title="Sit still" subtitle="Avoid moving or talking during the scan" /></Item></Card>
      <Card><Item><Meta title="Face the light" subtitle="Make sure light falls evenly on the face" /></Item></Card>
      <Card><Item><Meta title="Remove glasses" subtitle="If possible, for a clearer reading" /></Item></Card>
      <Card><Item><Meta title="Takes 30 seconds" subtitle="Stay in frame until the ring completes" /></Item></Card>
      <Note title="Processed on device">Video is never stored or uploaded.</Note>
      {permission === "denied" && (
        <Note tone="bad" title="Camera access is required">
          Grant camera permission in the browser to continue.
        </Note>
      )}
      <Cta disabled={permission !== "granted"} onClick={() => navigate("/4")}>
        Proceed to scan →
      </Cta>
    </>
  );
}
