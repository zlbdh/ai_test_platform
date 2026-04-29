/**
 * AnimatedOutlet — 页面切换过渡动画 (P2-1)
 * 
 * 纯 CSS 方案（无需 framer-motion 依赖）
 * 使用 React Router 的 useLocation 检测路由变化
 * 每次路由切换时触发 fade + slide-up 入场动画
 */
import React, { useEffect, useState, useRef } from 'react';
import { Outlet, useLocation } from 'react-router-dom';

interface AnimatedOutletProps {
    context?: unknown;
}

const AnimatedOutlet: React.FC<AnimatedOutletProps> = ({ context }) => {
    const location = useLocation();
    const [displayLocation, setDisplayLocation] = useState(location);
    const [transitionStage, setTransitionStage] = useState<'enter' | 'exit'>('enter');
    const prevPathRef = useRef(location.pathname);

    useEffect(() => {
        if (location.pathname !== prevPathRef.current) {
            // 路由变化 → 触发退出动画
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setTransitionStage('exit');
            prevPathRef.current = location.pathname;
        }
    }, [location]);

    const handleAnimationEnd = () => {
        if (transitionStage === 'exit') {
            // 退出动画完成 → 切换内容 → 触发入场动画
            setDisplayLocation(location);
            setTransitionStage('enter');
        }
    };

    return (
        <div
            className={`page-transition page-transition--${transitionStage}`}
            onAnimationEnd={handleAnimationEnd}
        >
            <Outlet key={displayLocation.pathname} context={context} />
        </div>
    );
};

export default AnimatedOutlet;
