import React from 'react';
import { Globe, Zap, Radio, Server } from '../icons';

export type ProtocolType = 'http' | 'graphql' | 'websocket' | 'grpc';

export interface RequestItem {
    id: string;
    name: string;
    method: string;
    url: string;
    headers: Record<string, string>;
    params: Record<string, string>;
    body: string;
    body_type: string;
    assertions: Assertion[];
    extract_variables: ExtractVar[];
}

export interface Assertion {
    type: 'status' | 'json_path' | 'header' | 'response_time' | 'body_contains';
    operator: string;
    expected: any;
    path?: string;
}

export interface ExtractVar {
    name: string;
    source: 'json' | 'header';
    path: string;
}

export interface Collection {
    id: string;
    name: string;
    description: string;
    requests: RequestItem[];
    request_count?: number;
    updated_at?: string;
}

export interface Environment {
    id: string;
    name: string;
    variables: Record<string, string>;
    is_active: boolean;
}

export interface RequestResult {
    request_id: string;
    request_name: string;
    success: boolean;
    status_code: number;
    response_time_ms: number;
    response_headers: Record<string, string>;
    response_body: string;
    assertions_passed: number;
    assertions_failed: number;
    assertion_details: any[];
    extracted_variables: Record<string, string>;
    error?: string;
}

export interface WSMessage {
    direction: string;
    content: any;
    timestamp: number;
    message_type: string;
}

export const METHOD_COLORS: Record<string, string> = {
    GET: 'text-green-500 bg-green-500/10',
    POST: 'text-yellow-500 bg-yellow-500/10',
    PUT: 'text-blue-500 bg-blue-500/10',
    PATCH: 'text-purple-500 bg-purple-500/10',
    DELETE: 'text-red-500 bg-red-500/10',
};

export const PROTOCOL_CONFIG: Record<ProtocolType, { label: string; icon: React.ReactNode; color: string }> = {
    http: { label: 'HTTP', icon: <Globe className="w-4 h-4" />, color: 'text-blue-500 bg-blue-500/10 border-blue-500/30' },
    graphql: { label: 'GraphQL', icon: <Zap className="w-4 h-4" />, color: 'text-pink-500 bg-pink-500/10 border-pink-500/30' },
    websocket: { label: 'WebSocket', icon: <Radio className="w-4 h-4" />, color: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/30' },
    grpc: { label: 'gRPC', icon: <Server className="w-4 h-4" />, color: 'text-orange-500 bg-orange-500/10 border-orange-500/30' },
};
