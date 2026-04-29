/**
 * Vitest Setup — DOM Matchers + Cleanup + jsdom polyfills
 */
import '@testing-library/jest-dom';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// jsdom missing API polyfills
Element.prototype.scrollIntoView = () => { };
window.matchMedia = window.matchMedia || function () {
    return { matches: false, addListener: () => { }, removeListener: () => { }, addEventListener: () => { }, removeEventListener: () => { }, dispatchEvent: () => true, media: '', onchange: null };
};
window.ResizeObserver = window.ResizeObserver || class { observe() { } unobserve() { } disconnect() { } };

// React Testing Library auto-cleanup after each test
afterEach(() => {
    cleanup();
});
