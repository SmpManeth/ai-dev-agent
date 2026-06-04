<?php

namespace App\Services;

use App\Models\AiAgentLog;
use App\Models\AiAgentTask;

class AiAgentLogService
{
    private const SECRET_PATTERNS = [
        '/(?:api[_-]?key|token|secret|password|authorization)\s*[=:]\s*["\']?[\w\-\.]+/i',
        '/Bearer\s+[A-Za-z0-9\-._~+\/]+=*/i',
        '/ghp_[A-Za-z0-9]{20,}/',
        '/xox[baprs]-[A-Za-z0-9\-]+/',
        '/sk-[A-Za-z0-9]{20,}/',
    ];

    public function log(
        AiAgentTask $task,
        string $message,
        string $level = 'info',
        ?string $step = null,
        ?array $context = null,
    ): AiAgentLog {
        return AiAgentLog::create([
            'ai_agent_task_id' => $task->id,
            'level' => $level,
            'step' => $step,
            'message' => $this->sanitize($message),
            'context' => $context ? $this->sanitizeContext($context) : null,
            'created_at' => now(),
        ]);
    }

    public function logProcessOutput(AiAgentTask $task, string $stream, string $content): void
    {
        $lines = preg_split('/\r\n|\r|\n/', $content) ?: [];
        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '') {
                continue;
            }
            $this->log($task, $line, $stream === 'stderr' ? 'error' : 'info', 'process', [
                'stream' => $stream,
            ]);
        }
    }

    public function sanitize(string $text): string
    {
        foreach (self::SECRET_PATTERNS as $pattern) {
            $text = preg_replace($pattern, '[REDACTED]', $text) ?? $text;
        }

        return $text;
    }

    public function sanitizeContext(array $context): array
    {
        $out = [];
        foreach ($context as $key => $value) {
            if (is_string($value)) {
                $out[$key] = $this->sanitize($value);
            } elseif (is_array($value)) {
                $out[$key] = $this->sanitizeContext($value);
            } else {
                $out[$key] = $value;
            }
        }

        return $out;
    }
}
