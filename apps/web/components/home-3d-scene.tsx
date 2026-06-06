"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

type OrbitNode = {
  mesh: THREE.Mesh;
  radius: number;
  speed: number;
  phase: number;
  height: number;
};

function makeRing(radius: number, color: string, rotation: [number, number, number]) {
  const geometry = new THREE.TorusGeometry(radius, 0.008, 12, 160);
  const material = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.3,
    blending: THREE.AdditiveBlending
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.rotation.set(rotation[0], rotation[1], rotation[2]);
  return mesh;
}

function addMesh(group: THREE.Group, mesh: THREE.Mesh) {
  group.add(mesh);
  return mesh;
}

function makeRoundedRectShape(width: number, height: number, radius: number) {
  const halfWidth = width / 2;
  const halfHeight = height / 2;
  const r = Math.min(radius, halfWidth, halfHeight);
  const shape = new THREE.Shape();
  shape.moveTo(-halfWidth + r, -halfHeight);
  shape.lineTo(halfWidth - r, -halfHeight);
  shape.quadraticCurveTo(halfWidth, -halfHeight, halfWidth, -halfHeight + r);
  shape.lineTo(halfWidth, halfHeight - r);
  shape.quadraticCurveTo(halfWidth, halfHeight, halfWidth - r, halfHeight);
  shape.lineTo(-halfWidth + r, halfHeight);
  shape.quadraticCurveTo(-halfWidth, halfHeight, -halfWidth, halfHeight - r);
  shape.lineTo(-halfWidth, -halfHeight + r);
  shape.quadraticCurveTo(-halfWidth, -halfHeight, -halfWidth + r, -halfHeight);
  return shape;
}

function makeRoundedExtrudeGeometry(width: number, height: number, radius: number, depth: number) {
  const geometry = new THREE.ExtrudeGeometry(makeRoundedRectShape(width, height, radius), {
    depth,
    bevelEnabled: true,
    bevelSegments: 8,
    bevelSize: 0.035,
    bevelThickness: 0.035
  });
  geometry.center();
  return geometry;
}

function makeShieldGeometry(depth: number) {
  const shape = new THREE.Shape();
  shape.moveTo(0, 1.08);
  shape.lineTo(0.64, 0.78);
  shape.lineTo(0.64, 0.22);
  shape.bezierCurveTo(0.64, -0.45, 0.38, -0.82, 0, -1.08);
  shape.bezierCurveTo(-0.38, -0.82, -0.64, -0.45, -0.64, 0.22);
  shape.lineTo(-0.64, 0.78);
  shape.lineTo(0, 1.08);
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: true,
    bevelSegments: 8,
    bevelSize: 0.035,
    bevelThickness: 0.035
  });
  geometry.center();
  return geometry;
}

export function Home3DScene() {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [showFallback, setShowFallback] = useState(false);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) {
      return;
    }

    const pauseMotion = new URLSearchParams(window.location.search).get("motion") === "off";
    if (!window.WebGLRenderingContext) {
      setShowFallback(true);
      return;
    }

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#03070d");
    scene.fog = new THREE.Fog("#03070d", 8, 23);

    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.set(0.2, 1.35, 8.2);
    camera.lookAt(0, 0.3, 0);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    } catch {
      setShowFallback(true);
      return;
    }
    renderer.setClearColor("#03070d", 1);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight("#9eeef0", 0.45);
    const keyLight = new THREE.PointLight("#49f2ff", 32, 12);
    keyLight.position.set(-2.8, 2.8, 4.2);
    const rimLight = new THREE.PointLight("#f3b95f", 18, 11);
    rimLight.position.set(3.5, 1.4, -2.5);
    scene.add(ambient, keyLight, rimLight);

    const rig = new THREE.Group();
    rig.position.set(1.55, 0.05, 0);
    scene.add(rig);

    const backplateMaterial = new THREE.MeshPhysicalMaterial({
      color: "#061018",
      emissive: "#04131c",
      emissiveIntensity: 0.28,
      metalness: 0.72,
      roughness: 0.34,
      transparent: true,
      opacity: 0.72,
      clearcoat: 1,
      clearcoatRoughness: 0.2
    });
    const shieldMaterial = new THREE.MeshPhysicalMaterial({
      color: "#0f766e",
      emissive: "#0a5f5a",
      emissiveIntensity: 0.24,
      metalness: 0.28,
      roughness: 0.18,
      transparent: true,
      opacity: 0.78,
      clearcoat: 1,
      clearcoatRoughness: 0.08
    });
    const centerMaterial = new THREE.MeshPhysicalMaterial({
      color: "#031316",
      emissive: "#06242b",
      emissiveIntensity: 0.52,
      metalness: 0.5,
      roughness: 0.2,
      clearcoat: 1
    });
    const coreMaterial = new THREE.MeshBasicMaterial({
      color: "#f6d365",
      transparent: true,
      opacity: 0.7,
      blending: THREE.AdditiveBlending
    });
    const sensorMaterial = new THREE.MeshBasicMaterial({
      color: "#a7f3d0",
      transparent: true,
      opacity: 0.54,
      blending: THREE.AdditiveBlending
    });
    const lineMaterial = new THREE.MeshBasicMaterial({
      color: "#73fbff",
      transparent: true,
      opacity: 0.28,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending
    });

    const logoGroup = new THREE.Group();
    logoGroup.rotation.z = -0.035;
    rig.add(logoGroup);

    const backplate = addMesh(logoGroup, new THREE.Mesh(makeRoundedExtrudeGeometry(1.92, 1.92, 0.36, 0.14), backplateMaterial));
    backplate.position.z = -0.08;

    const backplateRim = addMesh(logoGroup, new THREE.Mesh(new THREE.TorusGeometry(1.3, 0.012, 12, 180), lineMaterial));
    backplateRim.scale.set(1, 0.78, 1);
    backplateRim.position.z = 0.05;

    const shield = addMesh(logoGroup, new THREE.Mesh(makeShieldGeometry(0.22), shieldMaterial));
    shield.scale.set(1.02, 0.98, 1);
    shield.position.z = 0.06;

    const centerDisk = addMesh(logoGroup, new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.1, 72), centerMaterial));
    centerDisk.rotation.x = Math.PI / 2;
    centerDisk.position.z = 0.22;

    const core = addMesh(logoGroup, new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.12, 48), coreMaterial));
    core.rotation.x = Math.PI / 2;
    core.position.z = 0.31;

    const coreGlow = addMesh(logoGroup, new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.008, 12, 120), coreMaterial));
    coreGlow.position.z = 0.34;

    const sensorBarGeometry = new THREE.BoxGeometry(0.32, 0.045, 0.055);
    const leftSensor = addMesh(logoGroup, new THREE.Mesh(sensorBarGeometry, sensorMaterial));
    leftSensor.position.set(-0.5, 0, 0.32);
    const rightSensor = addMesh(logoGroup, new THREE.Mesh(sensorBarGeometry, sensorMaterial));
    rightSensor.position.set(0.5, 0, 0.32);
    const topSensor = addMesh(logoGroup, new THREE.Mesh(sensorBarGeometry, sensorMaterial));
    topSensor.rotation.z = Math.PI / 2;
    topSensor.position.set(0, 0.5, 0.32);
    const bottomSensor = addMesh(logoGroup, new THREE.Mesh(sensorBarGeometry, sensorMaterial));
    bottomSensor.rotation.z = Math.PI / 2;
    bottomSensor.position.set(0, -0.5, 0.32);

    const edgeGlow = addMesh(logoGroup, new THREE.Mesh(new THREE.TorusGeometry(0.46, 0.008, 12, 140), lineMaterial));
    edgeGlow.scale.set(1, 0.68, 1);
    edgeGlow.position.z = 0.35;

    const ringGroup = new THREE.Group();
    ringGroup.add(makeRing(1.16, "#26f7ff", [Math.PI / 2.55, 0, 0.18]));
    ringGroup.add(makeRing(1.58, "#5df0c8", [Math.PI / 2.2, 0.52, -0.22]));
    ringGroup.add(makeRing(2.04, "#ffcf73", [Math.PI / 2.85, -0.42, 0.48]));
    rig.add(ringGroup);

    const orbitNodes: OrbitNode[] = [];
    const nodeGeometry = new THREE.SphereGeometry(0.052, 18, 18);
    const nodeMaterial = new THREE.MeshBasicMaterial({
      color: "#9dfcff",
      transparent: true,
      opacity: 0.62,
      blending: THREE.AdditiveBlending
    });
    for (let index = 0; index < 14; index += 1) {
      const mesh = new THREE.Mesh(nodeGeometry, nodeMaterial);
      const radius = 1.22 + (index % 4) * 0.28;
      const phase = (index / 14) * Math.PI * 2;
      const height = ((index % 6) - 2.5) * 0.18;
      rig.add(mesh);
      orbitNodes.push({
        mesh,
        radius,
        phase,
        height,
        speed: 0.16 + (index % 5) * 0.035
      });
    }

    const particleCount = 520;
    const positions = new Float32Array(particleCount * 3);
    for (let index = 0; index < particleCount; index += 1) {
      const spread = index % 5 === 0 ? 11 : 7;
      positions[index * 3] = (Math.random() - 0.5) * spread;
      positions[index * 3 + 1] = (Math.random() - 0.4) * 5.2;
      positions[index * 3 + 2] = (Math.random() - 0.5) * 9.5;
    }
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const particles = new THREE.Points(
      particleGeometry,
      new THREE.PointsMaterial({
        color: "#77f7ff",
        size: 0.022,
        transparent: true,
        opacity: 0.46,
        depthWrite: false,
        blending: THREE.AdditiveBlending
      })
    );
    scene.add(particles);

    const grid = new THREE.GridHelper(16, 40, "#1dd7dd", "#102532");
    grid.position.set(0, -1.66, 0);
    const gridMaterial = grid.material as THREE.Material;
    gridMaterial.transparent = true;
    gridMaterial.opacity = 0.16;
    scene.add(grid);

    const floorGlow = new THREE.Mesh(
      new THREE.CircleGeometry(2.8, 96),
      new THREE.MeshBasicMaterial({
        color: "#0fd7df",
        transparent: true,
        opacity: 0.06,
        blending: THREE.AdditiveBlending
      })
    );
    floorGlow.rotation.x = -Math.PI / 2;
    floorGlow.position.y = -1.64;
    rig.add(floorGlow);

    const resize = () => {
      const width = host.clientWidth || window.innerWidth;
      const height = host.clientHeight || window.innerHeight;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.position.x = width < 720 ? 0 : 0.2;
      rig.position.x = width < 720 ? 1.78 : 1.86;
      rig.position.y = width < 720 ? -0.86 : -0.02;
      rig.scale.setScalar(width < 720 ? 0.42 : 0.9);
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();

    let animationFrame = 0;
    const startedAt = performance.now();
    const render = () => {
      const elapsed = (performance.now() - startedAt) / 1000;
      const motion = pauseMotion ? 0.18 : elapsed;
      logoGroup.rotation.y = Math.sin(motion * 0.42) * 0.1;
      logoGroup.position.y = Math.sin(motion * 1.05) * 0.035;
      shieldMaterial.emissiveIntensity = 0.22 + Math.sin(motion * 1.6) * 0.08;
      core.scale.setScalar(0.9 + Math.sin(motion * 2.2) * 0.08);
      coreGlow.rotation.z = motion * 0.64;
      coreGlow.scale.setScalar(0.96 + Math.sin(motion * 1.9) * 0.04);
      edgeGlow.rotation.z = -motion * 0.1;
      backplateRim.rotation.z = motion * 0.04;
      ringGroup.rotation.y = motion * 0.12;
      ringGroup.rotation.z = Math.sin(motion * 0.28) * 0.04;
      particles.rotation.y = motion * 0.035;
      floorGlow.scale.setScalar(1 + Math.sin(motion * 1.4) * 0.05);
      keyLight.intensity = 24 + Math.sin(motion * 1.7) * 3;

      orbitNodes.forEach((node, index) => {
        const angle = node.phase + motion * node.speed;
        node.mesh.position.set(
          Math.cos(angle) * node.radius,
          node.height + Math.sin(angle * 1.7 + index) * 0.16,
          Math.sin(angle) * node.radius * 0.42
        );
        node.mesh.scale.setScalar(0.82 + Math.sin(angle * 2.3) * 0.18);
      });

      renderer.render(scene, camera);
      if (!pauseMotion) {
        animationFrame = window.requestAnimationFrame(render);
      }
    };
    render();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      host.removeChild(renderer.domElement);
      const disposedGeometries = new Set<THREE.BufferGeometry>();
      const disposedMaterials = new Set<THREE.Material>();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Points || object instanceof THREE.LineSegments) {
          if (!disposedGeometries.has(object.geometry)) {
            object.geometry.dispose();
            disposedGeometries.add(object.geometry);
          }
          const material = object.material;
          if (Array.isArray(material)) {
            material.forEach((item) => {
              if (!disposedMaterials.has(item)) {
                item.dispose();
                disposedMaterials.add(item);
              }
            });
          } else if (!disposedMaterials.has(material)) {
            material.dispose();
            disposedMaterials.add(material);
          }
        }
      });
      renderer.dispose();
    };
  }, []);

  return (
    <div ref={hostRef} className="absolute inset-0" aria-hidden="true" data-testid="home-3d-scene">
      {showFallback && <Home3DFallback />}
    </div>
  );
}

function Home3DFallback() {
  return (
    <div className="absolute inset-0 overflow-hidden bg-[#03070d]" data-testid="home-3d-fallback">
      <div className="absolute left-[58%] top-[15%] h-[68%] w-[34%] min-w-64 -translate-x-1/2">
        <div className="absolute left-1/2 top-[20%] h-52 w-52 -translate-x-1/2 rounded-[26px] border border-cyan-100/14 bg-[#03070d]/80 shadow-[0_0_88px_rgba(45,212,191,0.22)]" />
        <div
          className="absolute left-1/2 top-[27%] h-36 w-32 -translate-x-1/2 bg-teal-600/70 shadow-[0_0_44px_rgba(20,184,166,0.26)]"
          style={{ clipPath: "polygon(50% 0%, 90% 18%, 90% 48%, 75% 78%, 50% 100%, 25% 78%, 10% 48%, 10% 18%)" }}
        />
        <div className="absolute left-1/2 top-[41%] h-16 w-16 -translate-x-1/2 rounded-full bg-[#031316] shadow-[inset_0_0_22px_rgba(45,212,191,0.18)]" />
        <div className="absolute left-1/2 top-[45%] h-7 w-7 -translate-x-1/2 rounded-full bg-amber-200/80 shadow-[0_0_26px_rgba(246,211,101,0.48)]" />
        <div className="absolute left-[35%] top-[48%] h-1.5 w-10 rounded-full bg-emerald-200/70 shadow-[0_0_12px_rgba(167,243,208,0.42)]" />
        <div className="absolute right-[35%] top-[48%] h-1.5 w-10 rounded-full bg-emerald-200/70 shadow-[0_0_12px_rgba(167,243,208,0.42)]" />
        <div className="absolute left-1/2 top-[34%] h-10 w-1.5 -translate-x-1/2 rounded-full bg-emerald-200/70 shadow-[0_0_12px_rgba(167,243,208,0.42)]" />
        <div className="absolute left-1/2 top-[58%] h-10 w-1.5 -translate-x-1/2 rounded-full bg-emerald-200/70 shadow-[0_0_12px_rgba(167,243,208,0.42)]" />
        <div className="absolute left-1/2 top-1/2 h-40 w-[24rem] -translate-x-1/2 -translate-y-1/2 rotate-[18deg] rounded-full border border-cyan-200/20" />
        <div className="absolute left-1/2 top-1/2 h-52 w-[30rem] -translate-x-1/2 -translate-y-1/2 -rotate-[22deg] rounded-full border border-teal-200/16" />
        <div className="absolute left-1/2 top-1/2 h-60 w-[34rem] -translate-x-1/2 -translate-y-1/2 rotate-[48deg] rounded-full border border-amber-200/12" />
        <div className="absolute inset-x-0 bottom-[9%] h-px bg-cyan-200/16 shadow-[0_0_32px_rgba(34,211,238,0.25)]" />
        <div className="absolute inset-x-[8%] bottom-[16%] grid grid-cols-8 gap-3 opacity-30">
          {Array.from({ length: 24 }).map((_, index) => (
            <span key={index} className="h-px bg-cyan-200/45" />
          ))}
        </div>
      </div>
    </div>
  );
}
