"use client";

import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { Float, Line, OrbitControls, RoundedBox, Text } from "@react-three/drei";
import { subsystemColor } from "@/lib/subsystems";

interface Props {
  subsystems: string[];
  highlighted: string[];
}

type Vec3 = [number, number, number];

function Node({
  position,
  label,
  color,
  active,
}: {
  position: Vec3;
  label: string;
  color: string;
  active: boolean;
}) {
  return (
    <Float speed={active ? 2.2 : 0} floatIntensity={active ? 0.45 : 0} rotationIntensity={0}>
      <group position={position}>
        <RoundedBox args={[0.95, 0.95, 0.95]} radius={0.14} smoothness={4}>
          <meshStandardMaterial
            color={color}
            emissive={active ? color : "#0b1020"}
            emissiveIntensity={active ? 0.9 : 0.05}
            metalness={0.35}
            roughness={0.3}
            transparent
            opacity={active ? 1 : 0.5}
          />
        </RoundedBox>
        <Text
          position={[0, -0.85, 0]}
          fontSize={0.2}
          color="#1e1b4b"
          anchorX="center"
          anchorY="top"
          maxWidth={2}
        >
          {label}
        </Text>
      </group>
    </Float>
  );
}

export default function Subsystem3D({ subsystems, highlighted }: Props) {
  const nodes = useMemo(() => {
    const n = subsystems.length || 1;
    return subsystems.map((s, i) => {
      const a = (i / n) * Math.PI * 2;
      const pos: Vec3 = [Math.cos(a) * 2.7, 0, Math.sin(a) * 2.7];
      return { name: s, pos, active: highlighted.some((h) => h.toLowerCase() === s.toLowerCase()) };
    });
  }, [subsystems, highlighted]);

  return (
    <Canvas
      camera={{ position: [0, 4.5, 6.5], fov: 42 }}
      dpr={[1, 2]}
      gl={{ alpha: true }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={0.75} />
      <pointLight position={[6, 9, 5]} intensity={1.3} />
      <pointLight position={[-5, -3, -5]} intensity={0.4} color="#a855f7" />
      <mesh>
        <icosahedronGeometry args={[0.42, 1]} />
        <meshStandardMaterial
          color="#6366f1"
          emissive="#6366f1"
          emissiveIntensity={0.6}
          metalness={0.4}
          roughness={0.2}
        />
      </mesh>
      {nodes.map((node) => (
        <group key={node.name}>
          {node.active && (
            <Line
              points={[[0, 0, 0], node.pos]}
              color="#6366f1"
              lineWidth={2}
              transparent
              opacity={0.7}
            />
          )}
          <Node
            position={node.pos}
            label={node.name}
            color={subsystemColor(node.name)}
            active={node.active}
          />
        </group>
      ))}
      <OrbitControls
        enablePan={false}
        enableZoom={false}
        autoRotate
        autoRotateSpeed={0.7}
        minPolarAngle={Math.PI / 4}
        maxPolarAngle={Math.PI / 1.8}
      />
    </Canvas>
  );
}
