"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { ReactNode } from "react";

/**
 * Procedural "blast-radius" assembly. Subsystems are mesh groups; the ones in
 * `highlighted` glow. Stylized (no real CAD) but mapped to the real subsystem
 * names, so a change affecting e.g. [chassis, power] lights those parts.
 */

export const SUBSYSTEM_COLOR: Record<string, string> = {
  chassis: "#9ca3af",
  power: "#34d399",
  firmware: "#60a5fa",
  qa: "#fbbf24",
  supply_chain: "#a78bfa",
  manufacturing: "#94a3b8",
  thermal: "#f87171",
};

function Part({
  subsystem,
  highlighted,
  children,
}: {
  subsystem: string;
  highlighted: boolean;
  children: (color: string, emissive: number) => ReactNode;
}) {
  const color = SUBSYSTEM_COLOR[subsystem] ?? "#cbd5e1";
  return <>{children(highlighted ? color : "#e5e7eb", highlighted ? 0.9 : 0.05)}</>;
}

function Box({
  args,
  position,
  color,
  emissive,
}: {
  args: [number, number, number];
  position: [number, number, number];
  color: string;
  emissive: number;
}) {
  return (
    <mesh position={position} castShadow receiveShadow>
      <boxGeometry args={args} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={emissive}
        metalness={0.2}
        roughness={0.6}
      />
    </mesh>
  );
}

function Assembly({ highlighted }: { highlighted: Set<string> }) {
  return (
    <group rotation={[0.2, 0.5, 0]}>
      {/* chassis — base plate + 4 corner posts */}
      <Part subsystem="chassis" highlighted={highlighted.has("chassis")}>
        {(c, e) => (
          <>
            <Box args={[3, 0.2, 2]} position={[0, -0.9, 0]} color={c} emissive={e} />
            {[
              [-1.3, 0, -0.8],
              [1.3, 0, -0.8],
              [-1.3, 0, 0.8],
              [1.3, 0, 0.8],
            ].map((p, i) => (
              <Box key={i} args={[0.15, 1.6, 0.15]} position={p as [number, number, number]} color={c} emissive={e} />
            ))}
          </>
        )}
      </Part>

      {/* power — battery cylinder + regulator */}
      <Part subsystem="power" highlighted={highlighted.has("power")}>
        {(c, e) => (
          <>
            <mesh position={[-0.8, -0.2, 0]}>
              <cylinderGeometry args={[0.4, 0.4, 1, 24]} />
              <meshStandardMaterial color={c} emissive={c} emissiveIntensity={e} metalness={0.3} roughness={0.5} />
            </mesh>
            <Box args={[0.5, 0.25, 0.5]} position={[0.3, -0.55, 0.4]} color={c} emissive={e} />
          </>
        )}
      </Part>

      {/* firmware — PCB plane + chips */}
      <Part subsystem="firmware" highlighted={highlighted.has("firmware")}>
        {(c, e) => (
          <>
            <Box args={[2.4, 0.06, 1.4]} position={[0.3, 0.1, 0]} color={c} emissive={e} />
            {[
              [0.9, 0.2, 0.3],
              [0.1, 0.2, -0.3],
              [1.0, 0.2, -0.3],
            ].map((p, i) => (
              <Box key={i} args={[0.3, 0.12, 0.3]} position={p as [number, number, number]} color={c} emissive={e} />
            ))}
          </>
        )}
      </Part>

      {/* qa — sensor spheres */}
      <Part subsystem="qa" highlighted={highlighted.has("qa")}>
        {(c, e) =>
          [
            [-1.0, 0.5, 0.7],
            [1.2, 0.5, -0.6],
          ].map((p, i) => (
            <mesh key={i} position={p as [number, number, number]}>
              <sphereGeometry args={[0.16, 16, 16]} />
              <meshStandardMaterial color={c} emissive={c} emissiveIntensity={e} />
            </mesh>
          ))
        }
      </Part>

      {/* supply_chain — edge connectors */}
      <Part subsystem="supply_chain" highlighted={highlighted.has("supply_chain")}>
        {(c, e) =>
          [
            [-1.5, 0.1, 0],
            [1.5, 0.1, 0.3],
          ].map((p, i) => (
            <mesh key={i} position={p as [number, number, number]} rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[0.1, 0.1, 0.4, 12]} />
              <meshStandardMaterial color={c} emissive={c} emissiveIntensity={e} />
            </mesh>
          ))
        }
      </Part>

      {/* manufacturing — top shell */}
      <Part subsystem="manufacturing" highlighted={highlighted.has("manufacturing")}>
        {(c, e) => <Box args={[2.8, 0.12, 1.8]} position={[0, 0.85, 0]} color={c} emissive={e} />}
      </Part>
    </group>
  );
}

export function AssemblyViewer({ highlighted }: { highlighted: string[] }) {
  const set = new Set(highlighted);
  return (
    <div className="h-full w-full rounded-xl bg-gradient-to-b from-zinc-900 to-zinc-800">
      <Canvas camera={{ position: [4, 3, 5], fov: 45 }} shadows dpr={[1, 2]}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 8, 5]} intensity={1.1} castShadow />
        <directionalLight position={[-5, 2, -5]} intensity={0.3} />
        <Assembly highlighted={set} />
        <OrbitControls enablePan={false} minDistance={4} maxDistance={12} autoRotate autoRotateSpeed={0.6} />
      </Canvas>
    </div>
  );
}
