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
  const geometry = new THREE.TorusGeometry(radius, 0.012, 12, 160);
  const material = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.68,
    blending: THREE.AdditiveBlending
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.rotation.set(rotation[0], rotation[1], rotation[2]);
  return mesh;
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

    const coreMaterial = new THREE.MeshPhysicalMaterial({
      color: "#16313f",
      emissive: "#0a5d67",
      emissiveIntensity: 0.85,
      metalness: 0.65,
      roughness: 0.26,
      clearcoat: 1,
      clearcoatRoughness: 0.16
    });
    const glassMaterial = new THREE.MeshPhysicalMaterial({
      color: "#54fbff",
      emissive: "#20dce4",
      emissiveIntensity: 1.8,
      metalness: 0,
      roughness: 0.08,
      transparent: true,
      opacity: 0.22,
      transmission: 0.45
    });
    const core = new THREE.Mesh(new THREE.CapsuleGeometry(0.58, 1.9, 12, 32), coreMaterial);
    core.rotation.z = 0.08;
    core.castShadow = false;
    const inner = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 2.55, 48), glassMaterial);
    rig.add(core, inner);

    const ringGroup = new THREE.Group();
    ringGroup.add(makeRing(1.28, "#26f7ff", [Math.PI / 2.55, 0, 0.18]));
    ringGroup.add(makeRing(1.78, "#5df0c8", [Math.PI / 2.2, 0.52, -0.22]));
    ringGroup.add(makeRing(2.22, "#ffcf73", [Math.PI / 2.85, -0.42, 0.48]));
    rig.add(ringGroup);

    const orbitNodes: OrbitNode[] = [];
    const nodeGeometry = new THREE.SphereGeometry(0.07, 18, 18);
    const nodeMaterial = new THREE.MeshBasicMaterial({
      color: "#9dfcff",
      transparent: true,
      opacity: 0.94,
      blending: THREE.AdditiveBlending
    });
    for (let index = 0; index < 18; index += 1) {
      const mesh = new THREE.Mesh(nodeGeometry, nodeMaterial);
      const radius = 1.42 + (index % 4) * 0.34;
      const phase = (index / 18) * Math.PI * 2;
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
        opacity: 0.58,
        depthWrite: false,
        blending: THREE.AdditiveBlending
      })
    );
    scene.add(particles);

    const grid = new THREE.GridHelper(16, 40, "#1dd7dd", "#102532");
    grid.position.set(0, -1.66, 0);
    const gridMaterial = grid.material as THREE.Material;
    gridMaterial.transparent = true;
    gridMaterial.opacity = 0.22;
    scene.add(grid);

    const floorGlow = new THREE.Mesh(
      new THREE.CircleGeometry(3.2, 96),
      new THREE.MeshBasicMaterial({
        color: "#0fd7df",
        transparent: true,
        opacity: 0.1,
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
      rig.position.x = width < 720 ? 0.45 : 1.55;
      rig.scale.setScalar(width < 720 ? 0.76 : 1);
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
      core.rotation.y = motion * 0.38;
      inner.rotation.y = -motion * 0.62;
      ringGroup.rotation.y = motion * 0.2;
      ringGroup.rotation.z = Math.sin(motion * 0.32) * 0.08;
      particles.rotation.y = motion * 0.035;
      floorGlow.scale.setScalar(1 + Math.sin(motion * 1.4) * 0.08);
      keyLight.intensity = 28 + Math.sin(motion * 1.7) * 4;

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
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Points || object instanceof THREE.LineSegments) {
          object.geometry.dispose();
          const material = object.material;
          if (Array.isArray(material)) {
            material.forEach((item) => item.dispose());
          } else {
            material.dispose();
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
        <div className="absolute left-1/2 top-[16%] h-[66%] w-24 -translate-x-1/2 rounded-full border border-cyan-200/30 bg-cyan-300/10 shadow-[0_0_80px_rgba(45,212,191,0.34)]" />
        <div className="absolute left-1/2 top-1/2 h-44 w-[26rem] -translate-x-1/2 -translate-y-1/2 rotate-[18deg] rounded-full border border-cyan-200/35" />
        <div className="absolute left-1/2 top-1/2 h-56 w-[32rem] -translate-x-1/2 -translate-y-1/2 -rotate-[22deg] rounded-full border border-teal-200/25" />
        <div className="absolute left-1/2 top-1/2 h-64 w-[36rem] -translate-x-1/2 -translate-y-1/2 rotate-[48deg] rounded-full border border-amber-200/20" />
        <div className="absolute inset-x-0 bottom-[9%] h-px bg-cyan-200/25 shadow-[0_0_40px_rgba(34,211,238,0.45)]" />
        <div className="absolute inset-x-[8%] bottom-[16%] grid grid-cols-8 gap-3 opacity-45">
          {Array.from({ length: 24 }).map((_, index) => (
            <span key={index} className="h-px bg-cyan-200/45" />
          ))}
        </div>
      </div>
    </div>
  );
}
