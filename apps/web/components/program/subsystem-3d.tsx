"use client";

import { Float, OrbitControls, RoundedBox, Text } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { subsystemColor } from "@/lib/subsystems";

interface Props {
  highlighted: string[];
}

type Vec3 = [number, number, number];

interface Part {
  key: string;
  label: string;
  match: string[];
  color: string;
}

const PARTS: Record<string, Part> = {
  base: {
    key: "base",
    label: "Chassis",
    match: ["chassis", "manufactur", "mfg", "frame"],
    color: subsystemColor("chassis"),
  },
  battery: {
    key: "battery",
    label: "Power / BMS",
    match: ["power", "bms", "battery", "energy", "cell"],
    color: subsystemColor("power"),
  },
  arm: {
    key: "arm",
    label: "Actuator",
    match: ["mech", "actuator", "arm", "motor", "torque", "bracket"],
    color: subsystemColor("bms"),
  },
  gripper: {
    key: "gripper",
    label: "Gripper",
    match: ["gripper", "end-effector", "manipul"],
    color: subsystemColor("supply"),
  },
  head: {
    key: "head",
    label: "Firmware / Sensors",
    match: ["firmware", "fw", "sensor", "qa", "thermal", "compliance"],
    color: subsystemColor("firmware"),
  },
};

function isActive(part: Part, highlighted: string[]): boolean {
  return highlighted.some((h) => part.match.some((m) => h.toLowerCase().includes(m)));
}

function Block({
  position,
  size,
  color,
  active,
  radius = 0.08,
}: {
  position: Vec3;
  size: Vec3;
  color: string;
  active: boolean;
  radius?: number;
}) {
  return (
    <RoundedBox position={position} args={size} radius={radius} smoothness={4}>
      <meshStandardMaterial
        color={active ? color : "#cbd2e0"}
        emissive={active ? color : "#0b1020"}
        emissiveIntensity={active ? 0.85 : 0.04}
        metalness={0.55}
        roughness={active ? 0.25 : 0.5}
      />
    </RoundedBox>
  );
}

function Robot({ highlighted }: { highlighted: string[] }) {
  const act = (k: keyof typeof PARTS) => isActive(PARTS[k], highlighted);
  const anyActive = Object.values(PARTS).some((p) => isActive(p, highlighted));

  return (
    <group position={[0, -1.2, 0]}>
      {/* mobile base + wheels */}
      <group>
        <Block
          position={[0, 0.35, 0]}
          size={[2.2, 0.5, 1.6]}
          color={PARTS.base.color}
          active={act("base")}
          radius={0.16}
        />
        {(
          [
            [0.85, 0.18, 0.6],
            [-0.85, 0.18, 0.6],
            [0.85, 0.18, -0.6],
            [-0.85, 0.18, -0.6],
          ] as Vec3[]
        ).map((p, i) => (
          <mesh key={i} position={p} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.22, 0.22, 0.18, 24]} />
            <meshStandardMaterial color="#1f2430" metalness={0.6} roughness={0.4} />
          </mesh>
        ))}
      </group>

      {/* torso column (battery / BMS) */}
      <Block
        position={[0, 1.5, 0]}
        size={[0.9, 1.7, 0.8]}
        color={PARTS.battery.color}
        active={act("battery")}
      />

      {/* head + eyes */}
      <group position={[0, 2.7, 0.05]}>
        <Block
          position={[0, 0, 0]}
          size={[0.9, 0.6, 0.7]}
          color={PARTS.head.color}
          active={act("head")}
          radius={0.12}
        />
        {(
          [
            [-0.2, 0.05, 0.36],
            [0.2, 0.05, 0.36],
          ] as Vec3[]
        ).map((p, i) => (
          <mesh key={i} position={p}>
            <sphereGeometry args={[0.07, 16, 16]} />
            <meshStandardMaterial color="#22d3ee" emissive="#22d3ee" emissiveIntensity={1.2} />
          </mesh>
        ))}
      </group>

      {/* arm: shoulder -> upper -> forearm -> gripper */}
      <group position={[0.55, 2.0, 0.2]}>
        <Block
          position={[0.35, 0, 0]}
          size={[0.9, 0.28, 0.28]}
          color={PARTS.arm.color}
          active={act("arm")}
        />
        <Block
          position={[0.85, -0.5, 0]}
          size={[0.26, 0.9, 0.26]}
          color={PARTS.arm.color}
          active={act("arm")}
        />
        <group position={[0.85, -1.05, 0]}>
          <Block
            position={[0.18, 0, 0.12]}
            size={[0.36, 0.16, 0.12]}
            color={PARTS.gripper.color}
            active={act("gripper")}
            radius={0.04}
          />
          <Block
            position={[0.18, 0, -0.12]}
            size={[0.36, 0.16, 0.12]}
            color={PARTS.gripper.color}
            active={act("gripper")}
            radius={0.04}
          />
        </group>
      </group>

      {/* label only when something is flagged */}
      {anyActive && (
        <Text
          position={[0, 4.0, 0]}
          fontSize={0.34}
          color="#4338ca"
          anchorX="center"
          anchorY="bottom"
        >
          Atlas v2
        </Text>
      )}
    </group>
  );
}

export default function Subsystem3D({ highlighted }: Props) {
  return (
    <Canvas
      camera={{ position: [4.5, 2, 6], fov: 42 }}
      dpr={[1, 2]}
      gl={{ alpha: true }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={0.85} />
      <pointLight position={[6, 9, 5]} intensity={1.4} />
      <pointLight position={[-6, 2, -4]} intensity={0.5} color="#818cf8" />
      <Float speed={1.1} floatIntensity={0.35} rotationIntensity={0}>
        <Robot highlighted={highlighted} />
      </Float>
      <OrbitControls
        enablePan={false}
        enableZoom={false}
        autoRotate
        autoRotateSpeed={0.7}
        minPolarAngle={Math.PI / 5}
        maxPolarAngle={Math.PI / 1.9}
      />
    </Canvas>
  );
}
