/* AnimatedOutlet: CSS route transitions.*/
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
            // A route change starts the exit transition.
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setTransitionStage('exit');
            prevPathRef.current = location.pathname;
        }
    }, [location]);

    const handleAnimationEnd = () => {
        if (transitionStage === 'exit') {
            // Enter the new content after the exit finishes.
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
