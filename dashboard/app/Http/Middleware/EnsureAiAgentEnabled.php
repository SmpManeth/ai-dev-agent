<?php

namespace App\Http\Middleware;

use App\Services\AiAgentHardeningService;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class EnsureAiAgentEnabled
{
    public function __construct(
        private readonly AiAgentHardeningService $hardening,
    ) {}

    public function handle(Request $request, Closure $next): Response
    {
        if ($request->routeIs('ai-agent.settings', 'ai-agent.settings.update')) {
            return $next($request);
        }

        if (! $this->hardening->isAgentEnabled()) {
            if ($request->expectsJson()) {
                return response()->json([
                    'error' => 'AI agent is disabled (kill switch). Enable it in Settings → Production hardening.',
                ], 503);
            }

            return redirect()
                ->route('ai-agent.settings', ['section' => 'production'])
                ->with('error', 'AI agent is disabled. Enable it in Production hardening settings.');
        }

        return $next($request);
    }
}
