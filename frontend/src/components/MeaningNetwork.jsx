import React, { useState, useEffect, useRef } from 'react';
import { Loader2, Award, Calendar, Compass, TrendingUp } from 'lucide-react';
import MeaningChange from './MeaningChange';

const EMOTION_FILTERS = [
  { key: 'all', label: '전체 은하', emoji: '🌌', color: 'var(--accent-primary)' },
  { key: 'happy', label: '행복', emoji: '😊', color: '#10b981' }, // Emerald
  { key: 'sad', label: '슬픔', emoji: '😢', color: '#6366f1' }, // Indigo
  { key: 'stressed', label: '스트레스', emoji: '🤯', color: '#ec4899' }, // Pink
  { key: 'calm', label: '평온', emoji: '🧘', color: '#06b6d4' }, // Cyan
  { key: 'tired', label: '피로', emoji: '😴', color: '#f59e0b' } // Amber
];

const MeaningNetwork = ({ token }) => {
  const [cards, setCards] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  const [activeFilter, setActiveFilter] = useState('all');
  const [activeTab, setActiveTab] = useState('explore'); // 'explore' | 'change'
  
  const canvasRef = useRef(null);
  const animationFrameRef = useRef(null);

  // 3D 회전 제어 변수 (Ref)
  const rotationRef = useRef({
    x: 0.3, // Y축 중심 회전각
    y: 0.2, // X축 중심 회전각
    targetX: 0.3,
    targetY: 0.2,
    autoRotateSpeed: 0.002
  });

  const mouseStateRef = useRef({
    isDown: false,
    startX: 0,
    startY: 0,
    currentX: 0,
    currentY: 0,
    hoveredNodeId: null
  });

  // 로컬에 계산된 3D 노드 정보 저장용 Ref
  const nodes3DRef = useRef([]);
  const backgroundStarsRef = useRef([]);
  const activeFilterRef = useRef('all');

  // 필터 상태 변경 시 Ref 동기화
  useEffect(() => {
    activeFilterRef.current = activeFilter;
  }, [activeFilter]);

  const themeColors = [
    '#6366f1', // Indigo (자아/성찰)
    '#10b981', // Emerald (성장/치유)
    '#f59e0b', // Amber (동기/에너지)
    '#ec4899', // Pink (관계/공감)
    '#06b6d4'  // Cyan (진리/지성)
  ];

  // API 데이터 패치
  useEffect(() => {
    const fetchValueCards = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/value-cards', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        if (response.ok) {
          const data = await response.json();
          setCards(data);
          if (data.length > 0) {
            setSelectedNode(data[0]);
            initialize3DData(data);
          }
        }
      } catch (err) {
        console.error('Error fetching value cards:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchValueCards();
    
    // 컴포넌트 언마운트 시 애니메이션 클린업
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [token]);

  // 3D 공간 데이터 초기화
  const initialize3DData = (cardsData) => {
    // 1. 배경용 성간 별가루(Background Stars) 생성
    const stars = [];
    for (let i = 0; i < 120; i++) {
      stars.push({
        x: (Math.random() - 0.5) * 800,
        y: (Math.random() - 0.5) * 800,
        z: (Math.random() - 0.5) * 800,
        size: Math.random() * 1.5 + 0.5,
        twinkleSpeed: 0.01 + Math.random() * 0.03,
        phase: Math.random() * Math.PI * 2
      });
    }
    backgroundStarsRef.current = stars;

    // 2. canonical 가치별 그룹화 및 클러스터 생성
    //    같은 가치를 다른 자유 키워드("자율성"/"자유"/"독립")로 적어도 한 클러스터로 모인다.
    //    canonical 이 없는(레거시·미분류) 카드는 keyword 로 그룹화(폴백).
    const groupKeyOf = (card) => card.canonical_value || card.keyword;
    const groups = {};
    cardsData.forEach(card => {
      const gkey = groupKeyOf(card);
      if (!groups[gkey]) {
        groups[gkey] = [];
      }
      groups[gkey].push(card);
    });

    const uniqueKeywords = Object.keys(groups);
    const nodes = [];

    // 키워드별로 3D 공간 상의 가상 클러스터 구체 중심점 배치
    const clusterCenters = {};
    const clusterSphereRadius = 220; // 대형 구체 반지름

    uniqueKeywords.forEach((kw, index) => {
      // 3D 구체 표면 상에 고르게 배치하기 위해 극좌표 사용
      const phi = Math.acos(-1 + (2 * index) / uniqueKeywords.length);
      const theta = Math.sqrt(uniqueKeywords.length * Math.PI) * phi;

      clusterCenters[kw] = {
        x: clusterSphereRadius * Math.sin(phi) * Math.cos(theta),
        y: clusterSphereRadius * Math.sin(phi) * Math.sin(theta),
        z: clusterSphereRadius * Math.cos(phi),
        colorIndex: index % themeColors.length
      };
    });

    // 개별 성찰 카드를 각 가치 클러스터 주변에 분산 배치
    cardsData.forEach(card => {
      const kw = groupKeyOf(card);
      const center = clusterCenters[kw];
      const itemsInGroup = groups[kw];
      const cardIndex = itemsInGroup.findIndex(item => item.id === card.id);

      let x, y, z;
      if (itemsInGroup.length === 1) {
        x = center.x;
        y = center.y;
        z = center.z;
      } else {
        // 클러스터 중심 주위로 작은 3D 원형 또는 구형 배치 추가
        const angle = (cardIndex / itemsInGroup.length) * Math.PI * 2;
        const radius = 35 + Math.random() * 15; // 분산 반경
        
        x = center.x + radius * Math.cos(angle);
        y = center.y + radius * Math.sin(angle);
        z = center.z + (Math.random() - 0.5) * 20; // 미세 Z 깊이 분산
      }

      nodes.push({
        ...card,
        groupKey: kw, // canonical 가치(또는 폴백 keyword) — 클러스터·엣지 기준
        base3D: { x, y, z }, // 초기 3D 원본 좌표
        rotated3D: { x, y, z }, // 회전 후 3D 좌표
        projected2D: { x: 0, y: 0, visible: false }, // 화면에 투영된 2D 좌표
        color: themeColors[center.colorIndex],
        colorIndex: center.colorIndex,
        filterAlpha: 1.0 // 필터 전이(Transition) 애니메이션용 알파값
      });
    });

    nodes3DRef.current = nodes;
  };

  // Canvas 드로잉 및 3D 투영 애니메이션 루프
  useEffect(() => {
    if (isLoading || cards.length === 0) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const fov = 450; // 원근 뷰 시야각(Field of View)

    const resizeCanvas = () => {
      const rect = canvas.parentElement.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height || 500;
    };
    
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const render = () => {
      if (!canvas || !ctx) return;
      
      const width = canvas.width;
      const height = canvas.height;
      const centerX = width / 2;
      const centerY = height / 2;

      // 캔버스 초기화
      ctx.fillStyle = '#060713';
      ctx.fillRect(0, 0, width, height);

      // 드래그 마우스 무빙 각도 보간(Interpolation)
      const rot = rotationRef.current;
      if (!mouseStateRef.current.isDown) {
        // 마우스 드래그를 안 할 때는 서서히 자동 회전
        rot.targetX += rot.autoRotateSpeed;
      }
      rot.x += (rot.targetX - rot.x) * 0.1;
      rot.y += (rot.targetY - rot.y) * 0.1;

      // 삼각함수 미리 계산
      const cosX = Math.cos(rot.y);
      const sinX = Math.sin(rot.y);
      const cosY = Math.cos(rot.x);
      const sinY = Math.sin(rot.x);

      // 1. 성간 별빛 배경(Stars Background) 3D 렌더링
      const stars = backgroundStarsRef.current;
      stars.forEach(star => {
        let x1 = star.x * cosY - star.z * sinY;
        let z1 = star.z * cosY + star.x * sinY;
        let y2 = star.y * cosX - z1 * sinX;
        let z2 = z1 * cosX + star.y * sinX;

        const scale = fov / (fov + z2 + 300); 
        const screenX = centerX + x1 * scale;
        const screenY = centerY + y2 * scale;

        if (screenX >= 0 && screenX <= width && screenY >= 0 && screenY <= height && z2 > -fov) {
          star.phase += star.twinkleSpeed;
          const alpha = 0.2 + Math.abs(Math.sin(star.phase)) * 0.6;
          
          ctx.beginPath();
          ctx.arc(screenX, screenY, star.size * scale, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
          ctx.fill();
        }
      });

      // 2. 3D 노드 좌표 회전 및 원근 투영 적용
      const nodes = nodes3DRef.current;
      const currentFilter = activeFilterRef.current;

      nodes.forEach(node => {
        let x1 = node.base3D.x * cosY - node.base3D.z * sinY;
        let z1 = node.base3D.z * cosY + node.base3D.x * sinY;
        let y2 = node.base3D.y * cosX - z1 * sinX;
        let z2 = z1 * cosX + node.base3D.y * sinX;

        node.rotated3D = { x: x1, y: y2, z: z2 };

        const scale = fov / (fov + z2 + 250); 
        const screenX = centerX + x1 * scale;
        const screenY = centerY + y2 * scale;

        node.projected2D = {
          x: screenX,
          y: screenY,
          scale: scale,
          visible: z2 > -fov
        };

        // 감정 필터링 가중치 보간 연산 (Fade In/Out 애니메이션)
        const isMatched = currentFilter === 'all' || node.emotion === currentFilter;
        const targetAlpha = isMatched ? 1.0 : 0.12; // 필터 제외 시 반투명화
        node.filterAlpha += (targetAlpha - node.filterAlpha) * 0.08;
      });

      // 3. 별자리 선(Edges) 3D 그리기
      ctx.lineWidth = 1;
      
      const uniqueKeywords = [...new Set(nodes.map(n => n.groupKey))];
      uniqueKeywords.forEach(kw => {
        const groupNodes = nodes.filter(n => n.groupKey === kw);
        const groupColor = groupNodes[0]?.color;

        for (let i = 0; i < groupNodes.length; i++) {
          for (let j = i + 1; j < groupNodes.length; j++) {
            const nA = groupNodes[i];
            const nB = groupNodes[j];

            if (nA.projected2D.visible && nB.projected2D.visible) {
              const isHighlighted = selectedNode && (selectedNode.id === nA.id || selectedNode.id === nB.id);
              const isHovered = mouseStateRef.current.hoveredNodeId === nA.id || mouseStateRef.current.hoveredNodeId === nB.id;

              // 원근에 따른 선 투명도 및 필터 투명도 결합
              const avgZ = (nA.rotated3D.z + nB.rotated3D.z) / 2;
              const zAlpha = Math.max(0.05, 1 - (avgZ + 250) / 500);
              const filterAlpha = (nA.filterAlpha + nB.filterAlpha) / 2; // 선 양끝 노드 필터 알파 평균

              ctx.beginPath();
              ctx.moveTo(nA.projected2D.x, nA.projected2D.y);
              ctx.lineTo(nB.projected2D.x, nB.projected2D.y);
              
              if (isHighlighted || isHovered) {
                ctx.strokeStyle = `rgba(${hexToRgb(groupColor)}, ${filterAlpha})`;
                ctx.lineWidth = 2.0;
                ctx.setLineDash([]);
                ctx.stroke();
              } else {
                ctx.strokeStyle = `rgba(${hexToRgb(groupColor)}, ${zAlpha * 0.35 * filterAlpha})`;
                ctx.lineWidth = 0.8;
                ctx.setLineDash([2, 4]); 
                ctx.stroke();
              }
            }
          }
        }
      });

      // 4. 노드 그리기 (깊이 역순 정렬)
      const sortedNodes = [...nodes].sort((a, b) => b.rotated3D.z - a.rotated3D.z);
      
      sortedNodes.forEach(node => {
        if (!node.projected2D.visible) return;

        const { x, y, scale } = node.projected2D;
        const isSelected = selectedNode && selectedNode.id === node.id;
        const isHovered = mouseStateRef.current.hoveredNodeId === node.id;

        // 원근 깊이 불투명도에 필터 알파(filterAlpha)를 최종 곱함
        const baseRadius = isSelected ? 9 : isHovered ? 7.5 : 5.5;
        const radius = baseRadius * scale;
        const depthOpacity = Math.max(0.2, Math.min(1.0, 1 - (node.rotated3D.z + 100) / 400));
        const finalOpacity = depthOpacity * node.filterAlpha;

        // 필터링에서 제외되고 호버되지 않은 노드는 클릭 차단
        const isInteractive = currentFilter === 'all' || node.emotion === currentFilter || isHovered;

        // 4-1. 선택/호버 시 네온 빛 후광 글로우 효과 (Canvas shadow 기능 사용)
        if ((isSelected || isHovered) && node.filterAlpha > 0.3) {
          ctx.save();
          ctx.shadowBlur = isSelected ? 22 : 14;
          ctx.shadowColor = node.color;
          
          ctx.beginPath();
          ctx.arc(x, y, radius * 2.2, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${hexToRgb(node.color)}, 0.15)`;
          ctx.fill();
          ctx.restore();
        }

        // 4-2. 코어 원 그리기
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = isSelected 
          ? '#ffffff' 
          : `rgba(${hexToRgb(node.color)}, ${finalOpacity})`;
        
        ctx.strokeStyle = `rgba(255, 255, 255, ${node.filterAlpha})`;
        ctx.lineWidth = isSelected ? 2 : 0.5;
        ctx.stroke();
        ctx.fill();

        // 4-3. 텍스트 라벨 그리기 (선택 또는 호버된 경우에만 띄움)
        if ((isSelected || isHovered) && node.filterAlpha > 0.3) {
          ctx.font = `bold ${isSelected ? '12px' : '10px'} Inter, sans-serif`;
          ctx.fillStyle = '#ffffff';
          ctx.textAlign = 'center';
          
          const text = node.keyword;
          const textWidth = ctx.measureText(text).width;
          ctx.fillStyle = 'rgba(10, 11, 26, 0.85)';
          ctx.fillRect(x - textWidth/2 - 6, y - radius - 20, textWidth + 12, 18);
          
          ctx.strokeStyle = `rgba(${hexToRgb(node.color)}, 0.5)`;
          ctx.lineWidth = 1;
          ctx.strokeRect(x - textWidth/2 - 6, y - radius - 20, textWidth + 12, 18);

          ctx.fillStyle = '#ffffff';
          ctx.fillText(text, x, y - radius - 7);
        }
      });

      animationFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isLoading, cards, selectedNode, activeTab]);

  // 마우스 상호작용 관련 핸들러들
  const handleMouseDown = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    mouseStateRef.current = {
      ...mouseStateRef.current,
      isDown: true,
      startX: x,
      startY: y,
      currentX: x,
      currentY: y
    };
  };

  const handleMouseMove = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const state = mouseStateRef.current;

    // 1. 드래그 중일 경우 은하 3D 회전 제어
    if (state.isDown) {
      const dx = x - state.currentX;
      const dy = y - state.currentY;

      rotationRef.current.targetX += dx * 0.007; 
      rotationRef.current.targetY = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, rotationRef.current.targetY + dy * 0.007));

      state.currentX = x;
      state.currentY = y;
    }

    // 2. 마우스 호버(Hover) 중인 3D 노드 검출 (2D 투영점 거리 계산)
    let hoveredNode = null;
    const nodes = nodes3DRef.current;
    const currentFilter = activeFilterRef.current;
    
    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      if (node.projected2D.visible) {
        // 필터링에 걸쳐서 활성화된 노드만 호버를 감지 (비활성 노드는 클릭 방지)
        const isMatched = currentFilter === 'all' || node.emotion === currentFilter;
        if (!isMatched) continue;

        const dx = x - node.projected2D.x;
        const dy = y - node.projected2D.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        if (dist < 12) {
          hoveredNode = node;
          break;
        }
      }
    }

    if (hoveredNode) {
      state.hoveredNodeId = hoveredNode.id;
      canvas.style.cursor = 'pointer';
    } else {
      state.hoveredNodeId = null;
      canvas.style.cursor = state.isDown ? 'grabbing' : 'grab';
    }
  };

  const handleMouseUpOrLeave = (e) => {
    const state = mouseStateRef.current;
    
    if (state.isDown) {
      const canvas = canvasRef.current;
      if (canvas && e.type === 'mouseup') {
        const rect = canvas.getBoundingClientRect();
        const endX = e.clientX - rect.left;
        const endY = e.clientY - rect.top;
        const distMoved = Math.sqrt(Math.pow(endX - state.startX, 2) + Math.pow(endY - state.startY, 2));

        if (distMoved < 5) {
          const nodes = nodes3DRef.current;
          const clickedNode = nodes.find(n => n.id === state.hoveredNodeId);
          if (clickedNode) {
            setSelectedNode(clickedNode);
          }
        }
      }
    }

    state.isDown = false;
    if (canvasRef.current) {
      canvasRef.current.style.cursor = 'grab';
    }
  };

  const hexToRgb = (hex) => {
    const cleanHex = hex.replace('#', '');
    const r = parseInt(cleanHex.substring(0, 2), 16);
    const g = parseInt(cleanHex.substring(2, 4), 16);
    const b = parseInt(cleanHex.substring(4, 6), 16);
    return `${r}, ${g}, ${b}`;
  };

  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString);
      return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일`;
    } catch (e) {
      return dateString;
    }
  };

  const downloadCardAsImage = (node) => {
    if (!node) return;

    const canvas = document.createElement('canvas');
    canvas.width = 800;
    canvas.height = 1200;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const emotionColorMap = {
      happy: '#10b981', 
      sad: '#6366f1', 
      stressed: '#ec4899', 
      calm: '#06b6d4', 
      tired: '#f59e0b' 
    };
    const themeColor = emotionColorMap[node.emotion] || '#6366f1';

    // 1. 우주 배경 그리기
    const bgGrad = ctx.createLinearGradient(0, 0, 0, 1200);
    bgGrad.addColorStop(0, '#0a0b1a');
    bgGrad.addColorStop(0.5, '#060713');
    bgGrad.addColorStop(1, '#020308');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, 800, 1200);

    // 1-1. 성간 오로라 광원 효과 추가
    const radialGrad = ctx.createRadialGradient(400, 500, 50, 400, 500, 400);
    radialGrad.addColorStop(0, hexToRgbAlpha(themeColor, 0.18));
    radialGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = radialGrad;
    ctx.fillRect(0, 0, 800, 1200);

    // 1-2. 무작위 별빛 파우더 드로잉
    ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
    for (let i = 0; i < 50; i++) {
      const x = Math.random() * 800;
      const y = Math.random() * 1200;
      const size = Math.random() * 1.8 + 0.5;
      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fill();
    }

    // 2. 글라스모피즘 카드 모양 그리기
    const cardX = 80;
    const cardY = 150;
    const cardW = 640;
    const cardH = 900;
    const cardR = 32;

    ctx.save();
    ctx.shadowColor = 'rgba(0, 0, 0, 0.55)';
    ctx.shadowBlur = 45;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 15;

    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(cardX, cardY, cardW, cardH, cardR);
    } else {
      drawRoundRectPolyfill(ctx, cardX, cardY, cardW, cardH, cardR);
    }
    ctx.fillStyle = 'rgba(255, 255, 255, 0.035)';
    ctx.fill();
    ctx.restore();

    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(cardX, cardY, cardW, cardH, cardR);
    } else {
      drawRoundRectPolyfill(ctx, cardX, cardY, cardW, cardH, cardR);
    }
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 3. 카드 상단 장식 별 렌더링
    ctx.save();
    ctx.shadowColor = themeColor;
    ctx.shadowBlur = 15;
    ctx.fillStyle = '#ffffff';
    drawStar(ctx, 400, 240, 4, 15, 6);
    ctx.restore();

    // 4. 타이틀 텍스트 렌더링
    ctx.fillStyle = 'rgba(255, 255, 255, 0.35)';
    ctx.font = '600 13px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('L O G O S  -  L O G   |   M E A N I N G   A R C H I V E', 400, 290);

    const emojiMap = { happy: '😊 행복', sad: '😢 슬픔', stressed: '🤯 스트레스', calm: '🧘 평온', tired: '😴 피로' };
    const emotionLabel = emojiMap[node.emotion] || '📝 성찰';
    ctx.fillStyle = hexToRgbAlpha(themeColor, 0.85);
    ctx.font = '700 14px Inter, sans-serif';
    ctx.fillText(`마음 온도: ${emotionLabel}`, 400, 330);

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.beginPath();
    ctx.moveTo(250, 370);
    ctx.lineTo(550, 370);
    ctx.stroke();

    // 4-1. 핵심 가치 키워드 (네온 글로우)
    ctx.save();
    ctx.shadowColor = themeColor;
    ctx.shadowBlur = 25;
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 58px Inter, system-ui, sans-serif';
    ctx.fillText(node.keyword, 400, 480);
    ctx.restore();

    // 4-2. 인사이트 본문 (다단 줄바꿈 연산)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.82)';
    ctx.font = '500 24px Inter, system-ui, sans-serif';
    const maxTextWidth = 460;
    const lineHeight = 42;
    const textYStart = 580;
    wrapText(ctx, node.insight, 400, textYStart, maxTextWidth, lineHeight);

    // 5. 하단 데코 및 브랜딩 날짜 표기
    ctx.fillStyle = 'rgba(255, 255, 255, 0.18)';
    ctx.font = '600 12px Inter, sans-serif';
    ctx.fillText('나의 마음 깊은 곳에서 건져 올린 실존 가치를 기록합니다.', 400, 930);

    const date = new Date(node.created_at);
    const dateStr = `${date.getFullYear()}. ${String(date.getMonth() + 1).padStart(2, '0')}. ${String(date.getDate()).padStart(2, '0')}.`;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.28)';
    ctx.font = '700 13px Inter, sans-serif';
    ctx.fillText(dateStr, 400, 970);

    // 6. 다운로드 트리거
    const dataUrl = canvas.toDataURL('image/png');
    const link = document.createElement('a');
    link.download = `[Logos-Log]_가치카드_${node.keyword}.png`;
    link.href = dataUrl;
    link.click();
  };

  const hexToRgbAlpha = (hex, alpha) => {
    const cleanHex = hex.replace('#', '');
    const r = parseInt(cleanHex.substring(0, 2), 16);
    const g = parseInt(cleanHex.substring(2, 4), 16);
    const b = parseInt(cleanHex.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  const drawRoundRectPolyfill = (ctx, x, y, width, height, radius) => {
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
  };

  const drawStar = (ctx, cx, cy, spikes, outerRadius, innerRadius) => {
    let rot = Math.PI / 2 * 3;
    let x = cx;
    let y = cy;
    let step = Math.PI / spikes;

    ctx.beginPath();
    ctx.moveTo(cx, cy - outerRadius);
    for (let i = 0; i < spikes; i++) {
      x = cx + Math.cos(rot) * outerRadius;
      y = cy + Math.sin(rot) * outerRadius;
      ctx.lineTo(x, y);
      rot += step;

      x = cx + Math.cos(rot) * innerRadius;
      y = cy + Math.sin(rot) * innerRadius;
      ctx.lineTo(x, y);
      rot += step;
    }
    ctx.lineTo(cx, cy - outerRadius);
    ctx.closePath();
    ctx.fill();
  };

  const wrapText = (ctx, text, x, y, maxWidth, lineHeight) => {
    const chars = text.split('');
    let line = '';
    let lines = [];

    for (let i = 0; i < chars.length; i++) {
      let testLine = line + chars[i];
      let testWidth = ctx.measureText(testLine).width;
      if (testWidth > maxWidth && i > 0) {
        lines.push(line);
        line = chars[i];
      } else {
        line = testLine;
      }
    }
    lines.push(line);

    for (let j = 0; j < lines.length; j++) {
      ctx.fillText(lines[j], x, y + (j * lineHeight));
    }
  };

  return (
    <div className="network-container">
      {isLoading ? (
        <div className="network-loading">
          <Loader2 className="animate-spin" size={32} color="var(--accent-primary)" />
          <p>은하수 성찰 네트워크를 형성하는 중...</p>
        </div>
      ) : (
        <>
        {/* 탐색(은하) / 변화(추이) 탭 전환 */}
        <div className="network-tabs" style={{ display: 'flex', gap: '8px', marginBottom: '16px', justifyContent: 'center' }}>
          {[
            { key: 'explore', label: '탐색 은하', Icon: Compass },
            { key: 'change', label: '변화 추이', Icon: TrendingUp },
          ].map(({ key, label, Icon }) => {
            const active = activeTab === key;
            return (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  padding: '8px 18px', borderRadius: '999px', cursor: 'pointer',
                  fontFamily: 'inherit', fontWeight: 600, fontSize: '0.86rem',
                  border: '1px solid var(--border-glass)',
                  background: active ? 'var(--accent-primary)' : 'rgba(255,255,255,0.04)',
                  color: active ? '#fff' : 'var(--text-muted)',
                  transition: 'all 0.25s',
                }}
              >
                <Icon size={15} />
                {label}
              </button>
            );
          })}
        </div>

        {activeTab === 'change' ? (
          <MeaningChange token={token} />
        ) : cards.length === 0 ? (
        <div className="network-empty-state">
          <div className="network-empty-icon">🌌</div>
          <h3>성찰 은하수가 아직 고요합니다</h3>
          <p>
            저널링을 완료하고 챗봇 대화방 상단에서<br />
            <strong>[💡 가치 카드로 저장하기]</strong>를 클릭해 나만의 3D 가치 별자리 노드를 우주에 띄워 보세요.
          </p>
        </div>
      ) : (
        <div className="network-layout">
          {/* 좌측: 3D 별자리 은하계 드래그 뷰포트 */}
          <div className="network-graph-panel 3d-viewport-panel" style={{ height: '500px', position: 'relative' }}>
            
            {/* 감정 은하수 필터 컨트롤러 */}
            <div className="emotion-filter-bar glass-panel" style={{ position: 'absolute', top: '15px', left: '15px', zIndex: 10, display: 'flex', gap: '8px', padding: '6px 10px', borderRadius: '20px', background: 'rgba(10, 11, 26, 0.6)', border: '1px solid rgba(255, 255, 255, 0.08)', flexWrap: 'wrap' }}>
              {EMOTION_FILTERS.map((filter) => {
                const isSelected = activeFilter === filter.key;
                const nodeCount = filter.key === 'all' 
                  ? cards.length 
                  : cards.filter(c => c.emotion === filter.key).length;

                return (
                  <button
                    key={filter.key}
                    onClick={() => {
                      setActiveFilter(filter.key);
                      // 필터를 전환하면 선택 노드를 그에 매칭되는 첫 번째로 임시 전환
                      const matched = filter.key === 'all' 
                        ? cards 
                        : cards.filter(c => c.emotion === filter.key);
                      if (matched.length > 0) {
                        setSelectedNode(matched[0]);
                      } else {
                        setSelectedNode(null);
                      }
                    }}
                    style={{
                      background: isSelected ? filter.color : 'transparent',
                      color: isSelected ? '#ffffff' : 'var(--text-muted)',
                      border: 'none',
                      padding: '4px 10px',
                      borderRadius: '15px',
                      fontSize: '0.78rem',
                      fontWeight: '600',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      transition: 'all 0.25s',
                      fontFamily: 'inherit',
                      boxShadow: isSelected ? `0 2px 10px ${filter.color}50` : 'none'
                    }}
                  >
                    <span>{filter.emoji}</span>
                    <span>{filter.label}</span>
                    <span style={{ fontSize: '0.65rem', opacity: 0.7 }}>({nodeCount})</span>
                  </button>
                );
              })}
            </div>

            <canvas
              ref={canvasRef}
              className="network-canvas-3d"
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUpOrLeave}
              onMouseLeave={handleMouseUpOrLeave}
              style={{ cursor: 'grab', width: '100%', height: '100%', display: 'block', borderRadius: '16px' }}
            />
            <div className="graph-instructions instruction-3d">
              <span>🖱️ 드래그하여 은하계를 3D 회전시키고, 노드를 클릭해 성찰을 감상하세요.</span>
            </div>
          </div>

          {/* 우측: 상세 가치 성찰 카드 피드백 */}
          {selectedNode ? (
            <div className="network-detail-panel glass-panel detail-3d animate-fade-in">
              <div className="detail-card-badge" style={{
                background: `rgba(${hexToRgb(selectedNode.color || '#6366f1')}, 0.15)`,
                borderColor: `rgba(${hexToRgb(selectedNode.color || '#6366f1')}, 0.3)`,
                color: selectedNode.color || 'var(--accent-primary)'
              }}>
                <Award size={14} />
                <span>성찰 가치 노드</span>
              </div>
              <h2 className="detail-card-keyword" style={{ color: selectedNode.color || 'var(--accent-primary)' }}>
                {selectedNode.keyword}
              </h2>
              
              <div className="detail-card-divider" />
              
              <div className="detail-card-insight-section">
                <p className="detail-card-insight">"{selectedNode.insight}"</p>
              </div>

              <div className="detail-card-footer" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div className="detail-card-date">
                  <Calendar size={12} />
                  <span>{formatDate(selectedNode.created_at)} 아카이브됨</span>
                </div>
                <button
                  type="button"
                  className="download-card-btn"
                  onClick={() => downloadCardAsImage(selectedNode)}
                  style={{
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid var(--border-glass)',
                    padding: '10px 16px',
                    borderRadius: '8px',
                    color: 'var(--text-main)',
                    fontWeight: '600',
                    cursor: 'pointer',
                    fontSize: '0.82rem',
                    fontFamily: 'inherit',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    transition: 'all 0.25s',
                    marginTop: '5px'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)';
                    e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                    e.currentTarget.style.borderColor = 'var(--border-glass)';
                  }}
                >
                  📥 성찰 카드 다운로드 (소장)
                </button>
              </div>
            </div>
          ) : (
            <div className="network-detail-panel glass-panel detail-3d animate-fade-in" style={{ justifyContent: 'center', alignItems: 'center', color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '15px' }}>🌌</div>
              <p style={{ fontSize: '0.88rem', lineHeight: '1.6' }}>
                선택된 감정 필터(<strong>{EMOTION_FILTERS.find(f => f.key === activeFilter)?.label}</strong>)에 속한<br />
                가치 노드가 성찰 은하에 아직 존재하지 않습니다.
              </p>
            </div>
          )}
        </div>
        )}
        </>
      )}
    </div>
  );
};

export default MeaningNetwork;
