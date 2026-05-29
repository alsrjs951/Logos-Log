import React, { useState, useEffect, useRef } from 'react';
import { Loader2, Award, Calendar } from 'lucide-react';

const MeaningNetwork = () => {
  const [cards, setCards] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const svgRef = useRef(null);

  // SVG 크기 정의
  const width = 600;
  const height = 500;

  useEffect(() => {
    const fetchValueCards = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/value-cards');
        if (response.ok) {
          const data = await response.json();
          setCards(data);
          if (data.length > 0) {
            // 첫 번째 카드를 기본 선택
            setSelectedNode(data[0]);
          }
        }
      } catch (err) {
        console.error('Error fetching value cards:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchValueCards();
  }, []);

  // 카드 데이터를 노드와 링크 구조로 변환 및 위치 할당
  const computeConstellation = () => {
    if (cards.length === 0) return { nodes: [], links: [] };

    // 1. 키워드별 그룹화
    const groups = {};
    cards.forEach(card => {
      if (!groups[card.keyword]) {
        groups[card.keyword] = [];
      }
      groups[card.keyword].push(card);
    });

    const uniqueKeywords = Object.keys(groups);
    const centerKeywords = {};
    
    // 2. 키워드 중심(클러스터 센터) 좌표 계산 (원형 배치)
    const clusterRadius = 160;
    const centerX = width / 2;
    const centerY = height / 2;

    uniqueKeywords.forEach((kw, index) => {
      const angle = (index / uniqueKeywords.length) * 2 * Math.PI - Math.PI / 2;
      centerKeywords[kw] = {
        cx: centerX + clusterRadius * Math.cos(angle),
        cy: centerY + clusterRadius * Math.sin(angle),
        angle: angle
      };
    });

    // 3. 개별 노드 위치 설정 (중심 주위로 분산)
    const nodes = [];
    const links = [];

    cards.forEach((card) => {
      const kw = card.keyword;
      const center = centerKeywords[kw];
      const itemsInGroup = groups[kw];
      const cardIndexInGroup = itemsInGroup.findIndex(item => item.id === card.id);
      
      let x, y;
      if (itemsInGroup.length === 1) {
        x = center.cx;
        y = center.cy;
      } else {
        // 그룹에 아이템이 여러 개일 경우 센터 주위로 회전 반경 계산
        const itemAngle = (cardIndexInGroup / itemsInGroup.length) * 2 * Math.PI;
        const spreadRadius = 35; // 확산 크기
        x = center.cx + spreadRadius * Math.cos(itemAngle);
        y = center.cy + spreadRadius * Math.sin(itemAngle);
      }

      nodes.push({
        ...card,
        x,
        y,
        colorIndex: uniqueKeywords.indexOf(kw) % 5 // 테마 색 지정을 위해
      });
    });

    // 4. 동일 키워드를 가진 노드들을 엣지(링크)로 연결
    uniqueKeywords.forEach((kw) => {
      const groupNodes = nodes.filter(n => n.keyword === kw);
      for (let i = 0; i < groupNodes.length; i++) {
        for (let j = i + 1; j < groupNodes.length; j++) {
          links.push({
            id: `${groupNodes[i].id}-${groupNodes[j].id}`,
            source: groupNodes[i],
            target: groupNodes[j],
            keyword: kw
          });
        }
      }
    });

    return { nodes, links };
  };

  const { nodes, links } = computeConstellation();

  const themeColors = [
    '#6366f1', // Indigo
    '#10b981', // Emerald
    '#f59e0b', // Amber
    '#ec4899', // Pink
    '#06b6d4'  // Cyan
  ];

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
          <p>나의 의미 네트워크 성찰 노드를 불러오는 중...</p>
        </div>
      ) : cards.length === 0 ? (
        <div className="network-empty-state">
          <div className="network-empty-icon">🌐</div>
          <h3>아카이브가 아직 비어 있습니다</h3>
          <p>
            저널링을 완료하고 챗봇 대화방 상단에서<br />
            <strong>[💡 가치 카드로 저장하기]</strong>를 클릭해 나의 실존 성찰 노드를 형성해 보세요.
          </p>
        </div>
      ) : (
        <div className="network-layout">
          {/* 좌측: constellaton 그래프 영역 */}
          <div className="network-graph-panel">
            <svg 
              ref={svgRef}
              width="100%" 
              height="100%" 
              viewBox={`0 0 ${width} ${height}`}
              className="network-svg"
            >
              {/* 네온 글로우 효과 필터 정의 */}
              <defs>
                <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur stdDeviation="6" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              {/* 1. 배경 링크 (엣지) 그리기 */}
              <g className="links-group">
                {links.map((link) => {
                  const color = themeColors[nodes.find(n => n.keyword === link.keyword)?.colorIndex || 0];
                  const isHighlighted = selectedNode && (selectedNode.id === link.source.id || selectedNode.id === link.target.id);
                  return (
                    <line
                      key={link.id}
                      x1={link.source.x}
                      y1={link.source.y}
                      x2={link.target.x}
                      y2={link.target.y}
                      stroke={color}
                      strokeWidth={isHighlighted ? 2.5 : 1}
                      strokeOpacity={isHighlighted ? 0.8 : 0.25}
                      strokeDasharray={isHighlighted ? "none" : "3,3"}
                      style={{ transition: 'all 0.3s' }}
                    />
                  );
                })}
              </g>

              {/* 2. 개별 노드(별자리 점) 그리기 */}
              <g className="nodes-group">
                {nodes.map((node) => {
                  const isSelected = selectedNode && selectedNode.id === node.id;
                  const isHovered = hoveredNode && hoveredNode.id === node.id;
                  const color = themeColors[node.colorIndex];
                  
                  return (
                    <g 
                      key={node.id}
                      transform={`translate(${node.x}, ${node.y})`}
                      className="node-group-element"
                      onClick={() => setSelectedNode(node)}
                      onMouseEnter={() => setHoveredNode(node)}
                      onMouseLeave={() => setHoveredNode(null)}
                      style={{ cursor: 'pointer' }}
                    >
                      {/* 외부 아우라 후광 원 */}
                      <circle
                        r={isSelected ? 16 : isHovered ? 12 : 8}
                        fill={color}
                        fillOpacity={isSelected ? 0.35 : isHovered ? 0.2 : 0.0}
                        filter={isSelected || isHovered ? "url(#glow)" : "none"}
                        style={{ transition: 'all 0.3s' }}
                      />
                      {/* 중심 코어 노드 */}
                      <circle
                        r={isSelected ? 6 : 5}
                        fill={color}
                        stroke="#ffffff"
                        strokeWidth={isSelected ? 1.5 : 0}
                        style={{ transition: 'all 0.3s' }}
                      />
                    </g>
                  );
                })}
              </g>

              {/* 3. 키워드 라벨 그리기 (텍스트) */}
              <g className="labels-group">
                {nodes.map((node) => {
                  const isSelected = selectedNode && selectedNode.id === node.id;
                  const isHovered = hoveredNode && hoveredNode.id === node.id;
                  
                  if (!isSelected && !isHovered) return null;
                  
                  return (
                    <text
                      key={`label-${node.id}`}
                      x={node.x}
                      y={node.y - 18}
                      textAnchor="middle"
                      fill="#ffffff"
                      fontSize="10"
                      fontWeight="600"
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {node.keyword}
                    </text>
                  );
                })}
              </g>
            </svg>
            <div className="graph-instructions">노드를 클릭하여 해당 깨달음 카드를 열람하세요.</div>
          </div>

          {/* 우측: 상세 가치 카드 열람 패널 */}
          {selectedNode && (
            <div className="network-detail-panel glass-panel animate-fade-in">
              <div className="detail-card-badge">
                <Award size={14} />
                <span>성찰 가치 노드</span>
              </div>
              <h2 className="detail-card-keyword">{selectedNode.keyword}</h2>
              
              <div className="detail-card-divider" />
              
              <div className="detail-card-insight-section">
                <p className="detail-card-insight">"{selectedNode.insight}"</p>
              </div>

              <div className="detail-card-footer">
                <div className="detail-card-date">
                  <Calendar size={12} />
                  <span>{formatDate(selectedNode.created_at)} 아카이브</span>
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
