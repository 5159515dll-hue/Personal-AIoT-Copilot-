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

function addObject<T extends THREE.Object3D>(group: THREE.Group, object: T) {
  group.add(object);
  return object;
}

function makeRing(radius: number, color: string, rotation: [number, number, number], opacity = 0.16) {
  const geometry = new THREE.TorusGeometry(radius, 0.006, 10, 180);
  const material = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.rotation.set(rotation[0], rotation[1], rotation[2]);
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

function makeRoundedExtrudeGeometry(width: number, height: number, radius: number, depth: number, bevel = 0.03) {
  const geometry = new THREE.ExtrudeGeometry(makeRoundedRectShape(width, height, radius), {
    depth,
    bevelEnabled: true,
    bevelSegments: 10,
    bevelSize: bevel,
    bevelThickness: bevel
  });
  geometry.center();
  return geometry;
}

function makeShieldPlateGeometry(depth: number) {
  const shape = new THREE.Shape();
  shape.moveTo(0, 0.86);
  shape.lineTo(0.5, 0.62);
  shape.lineTo(0.5, 0.16);
  shape.bezierCurveTo(0.5, -0.34, 0.28, -0.64, 0, -0.84);
  shape.bezierCurveTo(-0.28, -0.64, -0.5, -0.34, -0.5, 0.16);
  shape.lineTo(-0.5, 0.62);
  shape.lineTo(0, 0.86);
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: true,
    bevelSegments: 8,
    bevelSize: 0.02,
    bevelThickness: 0.02
  });
  geometry.center();
  return geometry;
}

function makeShieldOutline(material: THREE.LineBasicMaterial) {
  const points = [
    new THREE.Vector3(0, 0.92, 0),
    new THREE.Vector3(0.54, 0.66, 0),
    new THREE.Vector3(0.54, 0.16, 0),
    new THREE.Vector3(0.42, -0.42, 0),
    new THREE.Vector3(0, -0.9, 0),
    new THREE.Vector3(-0.42, -0.42, 0),
    new THREE.Vector3(-0.54, 0.16, 0),
    new THREE.Vector3(-0.54, 0.66, 0),
    new THREE.Vector3(0, 0.92, 0)
  ];
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  return new THREE.Line(geometry, material);
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
    scene.fog = new THREE.Fog("#03070d", 9, 24);

    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    camera.position.set(0.1, 1.05, 8.4);
    camera.lookAt(0.1, 0.12, 0);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    } catch {
      setShowFallback(true);
      return;
    }
    renderer.setClearColor("#03070d", 1);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.65));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight("#9eeef0", 0.32);
    const keyLight = new THREE.PointLight("#67f5ff", 24, 13);
    keyLight.position.set(-2.8, 3.2, 4.8);
    const rimLight = new THREE.PointLight("#f0bb72", 13, 10);
    rimLight.position.set(3.2, 1.6, -2.5);
    const softLight = new THREE.PointLight("#6df7d0", 9, 9);
    softLight.position.set(1.1, -1.4, 3.6);
    scene.add(ambient, keyLight, rimLight, softLight);

    const rig = new THREE.Group();
    rig.position.set(1.76, 0, 0);
    scene.add(rig);

    const glassMaterial = new THREE.MeshPhysicalMaterial({
      color: "#0b151d",
      emissive: "#031017",
      emissiveIntensity: 0.16,
      metalness: 0.2,
      roughness: 0.18,
      transparent: true,
      opacity: 0.58,
      clearcoat: 1,
      clearcoatRoughness: 0.1
    });
    const innerGlassMaterial = new THREE.MeshPhysicalMaterial({
      color: "#082328",
      emissive: "#042127",
      emissiveIntensity: 0.22,
      metalness: 0.18,
      roughness: 0.22,
      transparent: true,
      opacity: 0.42,
      clearcoat: 1,
      clearcoatRoughness: 0.12
    });
    const graphiteMaterial = new THREE.MeshPhysicalMaterial({
      color: "#071015",
      emissive: "#041218",
      emissiveIntensity: 0.12,
      metalness: 0.62,
      roughness: 0.36,
      clearcoat: 0.8,
      clearcoatRoughness: 0.24
    });
    const shieldMaterial = new THREE.MeshPhysicalMaterial({
      color: "#0b514d",
      emissive: "#063633",
      emissiveIntensity: 0.16,
      metalness: 0.28,
      roughness: 0.24,
      transparent: true,
      opacity: 0.38,
      clearcoat: 1,
      clearcoatRoughness: 0.12
    });
    const traceMaterial = new THREE.MeshBasicMaterial({
      color: "#a5fff0",
      transparent: true,
      opacity: 0.42,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const traceDimMaterial = new THREE.MeshBasicMaterial({
      color: "#52d7ce",
      transparent: true,
      opacity: 0.26,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const amberMaterial = new THREE.MeshBasicMaterial({
      color: "#ffd28a",
      transparent: true,
      opacity: 0.68,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const outlineMaterial = new THREE.LineBasicMaterial({
      color: "#d4fff8",
      transparent: true,
      opacity: 0.26,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const logoGroup = new THREE.Group();
    logoGroup.rotation.set(-0.12, -0.32, Math.PI / 4);
    rig.add(logoGroup);

    const shadowPlate = addObject(
      logoGroup,
      new THREE.Mesh(makeRoundedExtrudeGeometry(2.12, 2.12, 0.42, 0.09, 0.025), graphiteMaterial)
    );
    shadowPlate.position.z = -0.16;
    shadowPlate.scale.set(1.04, 1.04, 1);

    const glassPlate = addObject(
      logoGroup,
      new THREE.Mesh(makeRoundedExtrudeGeometry(1.98, 1.98, 0.4, 0.14, 0.035), glassMaterial)
    );
    glassPlate.position.z = -0.06;

    const innerPlate = addObject(
      logoGroup,
      new THREE.Mesh(makeRoundedExtrudeGeometry(1.28, 1.28, 0.26, 0.08, 0.024), innerGlassMaterial)
    );
    innerPlate.position.z = 0.06;

    const plateRim = addObject(logoGroup, makeRing(1.38, "#bffff5", [0, 0, 0], 0.1));
    plateRim.scale.set(1, 0.72, 1);
    plateRim.position.z = 0.12;

    const shield = addObject(logoGroup, new THREE.Mesh(makeShieldPlateGeometry(0.08), shieldMaterial));
    shield.scale.set(0.9, 0.9, 1);
    shield.position.z = 0.12;

    const shieldOutline = addObject(logoGroup, makeShieldOutline(outlineMaterial));
    shieldOutline.scale.set(0.98, 0.98, 1);
    shieldOutline.position.z = 0.2;

    const coreBase = addObject(logoGroup, new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.08, 64), graphiteMaterial));
    coreBase.rotation.x = Math.PI / 2;
    coreBase.position.z = 0.24;

    const coreGlass = addObject(
      logoGroup,
      new THREE.Mesh(makeRoundedExtrudeGeometry(0.36, 0.36, 0.08, 0.075, 0.012), innerGlassMaterial)
    );
    coreGlass.position.z = 0.3;

    const core = addObject(logoGroup, new THREE.Mesh(new THREE.OctahedronGeometry(0.12, 1), traceMaterial));
    core.rotation.z = Math.PI / 4;
    core.position.z = 0.38;

    const coreWarm = addObject(logoGroup, new THREE.Mesh(new THREE.SphereGeometry(0.045, 24, 24), amberMaterial));
    coreWarm.position.z = 0.48;

    const horizontalTrace = new THREE.BoxGeometry(0.62, 0.022, 0.026);
    const verticalTrace = new THREE.BoxGeometry(0.022, 0.62, 0.026);
    const shortHorizontalTrace = new THREE.BoxGeometry(0.36, 0.014, 0.02);
    const shortVerticalTrace = new THREE.BoxGeometry(0.014, 0.36, 0.02);

    [
      { geometry: horizontalTrace, position: [-0.54, 0, 0.32], material: traceMaterial },
      { geometry: horizontalTrace, position: [0.54, 0, 0.32], material: traceMaterial },
      { geometry: verticalTrace, position: [0, 0.54, 0.32], material: traceMaterial },
      { geometry: verticalTrace, position: [0, -0.54, 0.32], material: traceMaterial },
      { geometry: shortHorizontalTrace, position: [-0.78, 0.16, 0.25], material: traceDimMaterial },
      { geometry: shortHorizontalTrace, position: [0.78, -0.16, 0.25], material: traceDimMaterial },
      { geometry: shortVerticalTrace, position: [-0.16, -0.78, 0.25], material: traceDimMaterial },
      { geometry: shortVerticalTrace, position: [0.16, 0.78, 0.25], material: traceDimMaterial }
    ].forEach((trace) => {
      const mesh = addObject(logoGroup, new THREE.Mesh(trace.geometry, trace.material));
      mesh.position.set(trace.position[0], trace.position[1], trace.position[2]);
    });

    const endpointGeometry = new THREE.CylinderGeometry(0.035, 0.035, 0.035, 32);
    [
      [-0.88, 0, 0.34],
      [0.88, 0, 0.34],
      [0, 0.88, 0.34],
      [0, -0.88, 0.34]
    ].forEach((position, index) => {
      const material = index < 2 ? amberMaterial : traceMaterial;
      const endpoint = addObject(logoGroup, new THREE.Mesh(endpointGeometry, material));
      endpoint.rotation.x = Math.PI / 2;
      endpoint.position.set(position[0], position[1], position[2]);
    });

    const signalGroup = new THREE.Group();
    signalGroup.add(makeRing(1.48, "#45f3ea", [Math.PI / 2.35, 0.2, 0.1], 0.1));
    signalGroup.add(makeRing(1.94, "#ffd18a", [Math.PI / 2.7, -0.34, 0.4], 0.055));
    rig.add(signalGroup);

    const orbitNodes: OrbitNode[] = [];
    const nodeGeometry = new THREE.SphereGeometry(0.038, 16, 16);
    const nodeMaterial = new THREE.MeshBasicMaterial({
      color: "#a5fff0",
      transparent: true,
      opacity: 0.38,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    for (let index = 0; index < 8; index += 1) {
      const mesh = new THREE.Mesh(nodeGeometry, nodeMaterial);
      const radius = 1.28 + (index % 3) * 0.28;
      const phase = (index / 8) * Math.PI * 2;
      const height = ((index % 4) - 1.5) * 0.13;
      rig.add(mesh);
      orbitNodes.push({
        mesh,
        radius,
        phase,
        height,
        speed: 0.1 + (index % 4) * 0.025
      });
    }

    const particleCount = 260;
    const positions = new Float32Array(particleCount * 3);
    for (let index = 0; index < particleCount; index += 1) {
      const spread = index % 6 === 0 ? 10 : 6.5;
      positions[index * 3] = (Math.random() - 0.5) * spread;
      positions[index * 3 + 1] = (Math.random() - 0.45) * 4.9;
      positions[index * 3 + 2] = (Math.random() - 0.5) * 9.2;
    }
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const particles = new THREE.Points(
      particleGeometry,
      new THREE.PointsMaterial({
        color: "#85f7ff",
        size: 0.016,
        transparent: true,
        opacity: 0.23,
        depthWrite: false,
        blending: THREE.AdditiveBlending
      })
    );
    scene.add(particles);

    const grid = new THREE.GridHelper(15, 36, "#2ee7e4", "#0f2330");
    grid.position.set(0, -1.66, 0);
    const gridMaterial = grid.material as THREE.Material;
    gridMaterial.transparent = true;
    gridMaterial.opacity = 0.075;
    scene.add(grid);

    const floorGlow = new THREE.Mesh(
      new THREE.CircleGeometry(2.6, 96),
      new THREE.MeshBasicMaterial({
        color: "#3af2e7",
        transparent: true,
        opacity: 0.035,
        blending: THREE.AdditiveBlending,
        depthWrite: false
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
      camera.position.x = width < 720 ? 0 : 0.12;
      rig.position.x = width < 720 ? 1.64 : 1.86;
      rig.position.y = width < 720 ? -0.78 : -0.02;
      rig.scale.setScalar(width < 720 ? 0.43 : 1.06);
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
      logoGroup.rotation.x = -0.12 + Math.sin(motion * 0.28) * 0.025;
      logoGroup.rotation.y = -0.32 + Math.sin(motion * 0.36) * 0.07;
      logoGroup.position.y = Math.sin(motion * 0.78) * 0.025;
      shieldMaterial.emissiveIntensity = 0.1 + Math.sin(motion * 1.1) * 0.025;
      core.scale.setScalar(0.96 + Math.sin(motion * 1.8) * 0.035);
      core.rotation.y = motion * 0.24;
      coreWarm.scale.setScalar(0.9 + Math.sin(motion * 1.6) * 0.08);
      signalGroup.rotation.y = motion * 0.06;
      signalGroup.rotation.z = Math.sin(motion * 0.18) * 0.025;
      particles.rotation.y = motion * 0.018;
      floorGlow.scale.setScalar(1 + Math.sin(motion * 1.1) * 0.035);
      keyLight.intensity = 21 + Math.sin(motion * 1.2) * 1.8;

      orbitNodes.forEach((node, index) => {
        const angle = node.phase + motion * node.speed;
        node.mesh.position.set(
          Math.cos(angle) * node.radius,
          node.height + Math.sin(angle * 1.35 + index) * 0.1,
          Math.sin(angle) * node.radius * 0.36
        );
        node.mesh.scale.setScalar(0.84 + Math.sin(angle * 2.1) * 0.12);
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
        if (
          object instanceof THREE.Mesh ||
          object instanceof THREE.Points ||
          object instanceof THREE.Line ||
          object instanceof THREE.LineSegments
        ) {
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
      <div className="absolute left-[62%] top-[18%] h-[62%] w-[32%] min-w-64 -translate-x-1/2">
        <div className="absolute left-1/2 top-[24%] h-56 w-56 -translate-x-1/2 rotate-45 rounded-[34px] border border-cyan-100/14 bg-[#071118]/58 shadow-[0_0_78px_rgba(45,212,191,0.14)]" />
        <div className="absolute left-1/2 top-[30%] h-36 w-36 -translate-x-1/2 rotate-45 rounded-[22px] border border-teal-100/16 bg-[#092329]/28 shadow-[inset_0_0_32px_rgba(45,212,191,0.1)]" />
        <div
          className="absolute left-1/2 top-[35%] h-28 w-24 -translate-x-1/2 rotate-45 border border-cyan-100/18 bg-teal-700/18"
          style={{ clipPath: "polygon(50% 0%, 88% 18%, 88% 50%, 73% 78%, 50% 100%, 27% 78%, 12% 50%, 12% 18%)" }}
        />
        <div className="absolute left-1/2 top-[44%] h-14 w-14 -translate-x-1/2 rotate-45 rounded-xl border border-cyan-100/14 bg-[#071015]/80 shadow-[inset_0_0_22px_rgba(45,212,191,0.12)]" />
        <div className="absolute left-1/2 top-[48%] h-5 w-5 -translate-x-1/2 rotate-45 rounded-md bg-teal-200/70 shadow-[0_0_20px_rgba(94,234,212,0.34)]" />
        <div className="absolute left-[37%] top-[49%] h-px w-12 rounded-full bg-cyan-100/36 shadow-[0_0_10px_rgba(165,255,240,0.22)]" />
        <div className="absolute right-[37%] top-[49%] h-px w-12 rounded-full bg-cyan-100/36 shadow-[0_0_10px_rgba(165,255,240,0.22)]" />
        <div className="absolute left-1/2 top-[37%] h-12 w-px -translate-x-1/2 rounded-full bg-cyan-100/30 shadow-[0_0_10px_rgba(165,255,240,0.18)]" />
        <div className="absolute left-1/2 top-[56%] h-12 w-px -translate-x-1/2 rounded-full bg-cyan-100/30 shadow-[0_0_10px_rgba(165,255,240,0.18)]" />
        <div className="absolute left-1/2 top-1/2 h-40 w-[24rem] -translate-x-1/2 -translate-y-1/2 rotate-[12deg] rounded-full border border-cyan-200/10" />
        <div className="absolute left-1/2 top-1/2 h-56 w-[31rem] -translate-x-1/2 -translate-y-1/2 -rotate-[20deg] rounded-full border border-amber-200/8" />
        <div className="absolute inset-x-[12%] bottom-[17%] h-px bg-cyan-200/10 shadow-[0_0_24px_rgba(34,211,238,0.14)]" />
        <div className="absolute inset-x-[14%] bottom-[22%] grid grid-cols-8 gap-4 opacity-18">
          {Array.from({ length: 16 }).map((_, index) => (
            <span key={index} className="h-px bg-cyan-200/36" />
          ))}
        </div>
      </div>
    </div>
  );
}
