<?php

namespace App\Services;

use App\Models\AiAgentAuditEvent;
use App\Models\AiAgentTask;

class AiAgentAuditService
{
    public function __construct(
        private readonly AiAgentLogService $logService,
    ) {}

    public function record(
        string $event,
        string $detail = '',
        string $level = 'info',
        ?AiAgentTask $task = null,
        ?array $context = null,
    ): AiAgentAuditEvent {
        return AiAgentAuditEvent::create([
            'ai_agent_task_id' => $task?->id,
            'event' => $event,
            'level' => $level,
            'detail' => $this->logService->sanitize($detail),
            'context' => $context ? $this->logService->sanitizeContext($context) : null,
            'created_at' => now(),
        ]);
    }
}
