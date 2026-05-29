import React, { useState, useEffect, useRef } from 'react';
import { Loader2, Award, Calendar } from 'lucide-react';

const MeaningNetwork = () => {
  const [cards, setCards] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  
  const canvasRef = useRef(null);
  const animationFrameRef = useRef(null);

  // 3D 회전 제어 변수 (Ref를 사용하여 리렌더링 없이 애니메이션 루프에서 즉각 반영)
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
        const response = await fetch('http://localhost:8000/api/value-cards');
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
  }, []);

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

    // 2. 키워드별 그룹화 및 클러스터 생성
    const groups = {};
    cardsData.forEach(card => {
      if (!groups[card.keyword]) {
        groups[card.keyword] = [];
      }
      groups[card.keyword].push(card);
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

    // 개별 성찰 카드를 각 키워드 클러스터 주변에 분산 배치
    cardsData.forEach(card => {
      const kw = card.keyword;
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
        base3D: { x, y, z }, // 초기 3D 원본 좌표
        rotated3D: { x, y, z }, // 회전 후 3D 좌표
        projected2D: { x: 0, y: 0, visible: false }, // 화면에 투영된 2D 좌표
        color: themeColors[center.colorIndex],
        colorIndex: center.colorIndex
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

      // 캔버스 초기화 (완전 블랙이 아닌, 약간의 네이비 아우라가 가미된 밤하늘 색)
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
        // Y축 회전
        let x1 = star.x * cosY - star.z * sinY;
        let z1 = star.z * cosY + star.x * sinY;
        // X축 회전
        let y2 = star.y * cosX - z1 * sinX;
        let z2 = z1 * cosX + star.y * sinX;

        // 원근 투영
        const scale = fov / (fov + z2 + 300); // 300은 Z-오프셋
        const screenX = centerX + x1 * scale;
        const screenY = centerY + y2 * scale;

        if (screenX >= 0 && screenX <= width && screenY >= 0 && screenY <= height && z2 > -fov) {
          // 반짝임 수치 계산 (Sin 파동)
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
      nodes.forEach(node => {
        // Y축 회전 (X, Z 좌표 변경)
        let x1 = node.base3D.x * cosY - node.base3D.z * sinY;
        let z1 = node.base3D.z * cosY + node.base3D.x * sinY;
        // X축 회전 (Y, Z 좌표 변경)
        let y2 = node.base3D.y * cosX - z1 * sinX;
        let z2 = z1 * cosX + node.base3D.y * sinX;

        node.rotated3D = { x: x1, y: y2, z: z2 };

        // 원근감 스케일 계산
        const scale = fov / (fov + z2 + 250); 
        const screenX = centerX + x1 * scale;
        const screenY = centerY + y2 * scale;

        node.projected2D = {
          x: screenX,
          y: screenY,
          scale: scale,
          visible: z2 > -fov // 너무 가까운(클리핑되는) 오브젝트 방지
        };
      });

      // 3. 별자리 선(Edges) 3D 그리기
      ctx.lineWidth = 1;
      
      // 동일 키워드끼리 연결선 형성
      const uniqueKeywords = [...new Set(nodes.map(n => n.keyword))];
      uniqueKeywords.forEach(kw => {
        const groupNodes = nodes.filter(n => n.keyword === kw);
        const groupColor = groupNodes[0]?.color;

        for (let i = 0; i < groupNodes.length; i++) {
          for (let j = i + 1; j < groupNodes.length; j++) {
            const nA = groupNodes[i];
            const nB = groupNodes[j];

            if (nA.projected2D.visible && nB.projected2D.visible) {
              // 선택되었거나 호버된 노드에 연관된 선이면 두껍게 강조
              const isHighlighted = selectedNode && (selectedNode.id === nA.id || selectedNode.id === nB.id);
              const isHovered = mouseStateRef.current.hoveredNodeId === nA.id || mouseStateRef.current.hoveredNodeId === nB.id;

              // 원근에 따른 선 투명도 조절
              const avgZ = (nA.rotated3D.z + nB.rotated3D.z) / 2;
              const zAlpha = Math.max(0.05, 1 - (avgZ + 250) / 500);

              ctx.beginPath();
              ctx.moveTo(nA.projected2D.x, nA.projected2D.y);
              ctx.lineTo(nB.projected2D.x, nB.projected2D.y);
              
              if (isHighlighted || isHovered) {
                ctx.strokeStyle = groupColor;
                ctx.lineWidth = 2.0;
                ctx.setLineDash([]);
                ctx.stroke();
              } else {
                ctx.strokeStyle = `rgba(${hexToRgb(groupColor)}, ${zAlpha * 0.35})`;
                ctx.lineWidth = 0.8;
                ctx.setLineDash([2, 4]); // 미려한 점선 연출
                ctx.stroke();
              }
            }
          }
        }
      });

      // 4. 노드 그리기 (깊이 역순 정렬: Z가 높은(깊은) 노드부터 렌더링하여 겹침 처리)
      const sortedNodes = [...nodes].sort((a, b) => b.rotated3D.z - a.rotated3D.z);
      
      sortedNodes.forEach(node => {
        if (!node.projected2D.visible) return;

        const { x, y, scale } = node.projected2D;
        const isSelected = selectedNode && selectedNode.id === node.id;
        const isHovered = mouseStateRef.current.hoveredNodeId === node.id;

        // 원근에 따른 크기 및 불투명도 보정
        const baseRadius = isSelected ? 9 : isHovered ? 7.5 : 5.5;
        const radius = baseRadius * scale;
        const opacity = Math.max(0.2, Math.min(1.0, 1 - (node.rotated3D.z + 100) / 400));

        // 4-1. 선택/호버 시 네온 빛 후광 글로우 효과 (Canvas shadow 기능 사용)
        if (isSelected || isHovered) {
          ctx.save();
          ctx.shadowBlur = isSelected ? 22 : 14;
          ctx.shadowColor = node.color;
          
          // 외부 아우라 서클
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
          : `rgba(${hexToRgb(node.color)}, ${opacity})`;
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = isSelected ? 2 : 0.5;
        ctx.stroke();
        ctx.fill();

        // 4-3. 텍스트 라벨 그리기 (선택 또는 호버된 경우에만 미려하게 띄움)
        if (isSelected || isHovered) {
          ctx.font = `bold ${isSelected ? '12px' : '10px'} Inter, sans-serif`;
          ctx.fillStyle = '#ffffff';
          ctx.textAlign = 'center';
          
          // 텍스트 배경 반투명 박스
          const text = node.keyword;
          const textWidth = ctx.measureText(text).width;
          ctx.fillStyle = 'rgba(10, 11, 26, 0.85)';
          ctx.fillRect(x - textWidth/2 - 6, y - radius - 20, textWidth + 12, 18);
          
          // 테두리 글로우 효과
          ctx.strokeStyle = `rgba(${hexToRgb(node.color)}, 0.5)`;
          ctx.lineWidth = 1;
          ctx.strokeRect(x - textWidth/2 - 6, y - radius - 20, textWidth + 12, 18);

          // 텍스트 드로잉
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
  }, [isLoading, cards, selectedNode]);

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

      rotationRef.current.targetX += dx * 0.007; // 드래그 회전 감도
      rotationRef.current.targetY = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, rotationRef.current.targetY + dy * 0.007));

      state.currentX = x;
      state.currentY = y;
    }

    // 2. 마우스 호버(Hover) 중인 3D 노드 검출 (2D 투영점 거리 계산)
    let hoveredNode = null;
    const nodes = nodes3DRef.current;
    
    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      if (node.projected2D.visible) {
        const dx = x - node.projected2D.x;
        const dy = y - node.projected2D.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        // 2D 스크린상 12px 이내에 들어오면 호버로 간주
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
    
    // 만약 드래그 거리가 극히 미세하다면 클릭(Click) 이벤트로 판별하여 노드 선택
    if (state.isDown) {
      const canvas = canvasRef.current;
      if (canvas && e.type === 'mouseup') {
        const rect = canvas.getBoundingClientRect();
        const endX = e.clientX - rect.left;
        const endY = e.clientY - rect.top;
        const distMoved = Math.sqrt(Math.pow(endX - state.startX, 2) + Math.pow(endY - state.startY, 2));

        if (distMoved < 5) {
          // 노드 클릭 판정
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

  // Hex 색상을 RGB 콤마 문자열로 파싱하는 헬퍼 함수
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

  return (
    <div className="network-container">
      {isLoading ? (
        <div className="network-loading">
          <Loader2 className="animate-spin" size={32} color="var(--accent-primary)" />
          <p>은하수 성찰 네트워크를 형성하는 중...</p>
        </div>
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
          {selectedNode && (
            <div className="network-detail-panel glass-panel detail-3d animate-fade-in">
              <div className="detail-card-badge">
                <Award size={14} />
                <span>성찰 가치 노드</span>
              </div>
              <h2 className="detail-card-keyword" style={{ color: selectedNode.color }}>
                {selectedNode.keyword}
              </h2>
              
              <div className="detail-card-divider" />
              
              <div className="detail-card-insight-section">
                <p className="detail-card-insight">"{selectedNode.insight}"</p>
              </div>

              <div className="detail-card-footer">
                <div className="detail-card-date">
                  <Calendar size={12} />
                  <span>{formatDate(selectedNode.created_at)} 아카이브됨</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MeaningNetwork;
