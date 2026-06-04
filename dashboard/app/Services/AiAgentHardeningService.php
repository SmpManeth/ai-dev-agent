<?php

namespace App\Services;

use Illuminate\Support\Facades\File;

class AiAgentHardeningService
{
    public const STORAGE_FILE = 'app/ai-agent-hardening.json';

    /**
     * @return array<string, mixed>
     */
    public function defaults(): array
    {
        $path = $this->projectDefaultsPath();
        if (! is_file($path)) {
            return $this->builtinDefaults();
        }

        $decoded = json_decode((string) file_get_contents($path), true);

        return is_array($decoded) ? $decoded : $this->builtinDefaults();
    }

    /**
     * @return array<string, mixed>
     */
    public function current(): array
    {
        $path = $this->storagePath();
        if (! File::exists($path)) {
            return $this->defaults();
        }

        $decoded = json_decode(File::get($path), true);
        if (! is_array($decoded)) {
            return $this->defaults();
        }

        return array_replace_recursive($this->defaults(), $decoded);
    }

    public function isAgentEnabled(): bool
    {
        return (bool) ($this->current()['agent_enabled'] ?? true);
    }

    public function hardeningConfigPath(): string
    {
        return $this->storagePath();
    }

    /**
     * @param  array<string, mixed>  $input
     * @return array<string, mixed>
     */
    public function save(array $input): array
    {
        $merged = array_replace_recursive($this->defaults(), $this->normalizeInput($input));
        File::ensureDirectoryExists(dirname($this->storagePath()));
        File::put($this->storagePath(), json_encode($merged, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));

        return $merged;
    }

    /**
     * @param  array<string, mixed>  $input
     * @return array<string, mixed>
     */
    private function normalizeInput(array $input): array
    {
        $bool = static fn (string $key, bool $default = false): bool => filter_var(
            $input[$key] ?? $default,
            FILTER_VALIDATE_BOOLEAN,
        );

        return [
            'agent_enabled' => $bool('agent_enabled', true),
            'sandbox_enabled' => $bool('sandbox_enabled', false),
            'sandbox_image' => trim((string) ($input['sandbox_image'] ?? 'ai-dev-agent-sandbox:latest')),
            'sandbox_network' => trim((string) ($input['sandbox_network'] ?? 'none')),
            'require_approval_before_pr' => $bool('require_approval_before_pr', false),
            'max_retries' => max(0, min(10, (int) ($input['max_retries'] ?? 3))),
            'max_runtime_minutes' => max(5, min(480, (int) ($input['max_runtime_minutes'] ?? 120))),
            'max_tokens_per_task' => max(10_000, (int) ($input['max_tokens_per_task'] ?? 500_000)),
            'risk_threshold' => in_array(
                strtolower((string) ($input['risk_threshold'] ?? 'medium')),
                ['low', 'medium', 'high'],
                true,
            ) ? strtolower((string) $input['risk_threshold']) : 'medium',
            'allowed_repositories' => $this->linesToList($input['allowed_repositories'] ?? ''),
            'blocked_file_patterns' => $this->linesToList(
                $input['blocked_file_patterns'] ?? '',
                $this->defaults()['blocked_file_patterns'] ?? [],
            ),
            'blocked_command_patterns' => $this->linesToList(
                $input['blocked_command_patterns'] ?? '',
                $this->defaults()['blocked_command_patterns'] ?? [],
            ),
            'allowed_command_prefixes' => $this->linesToList(
                $input['allowed_command_prefixes'] ?? '',
                $this->defaults()['allowed_command_prefixes'] ?? [],
            ),
        ];
    }

    /**
     * @param  list<string>  $fallback
     * @return list<string>
     */
    private function linesToList(mixed $value, array $fallback = []): array
    {
        if (is_array($value)) {
            $list = array_values(array_filter(array_map('strval', $value)));

            return $list !== [] ? $list : $fallback;
        }
        $text = trim((string) $value);
        if ($text === '') {
            return $fallback;
        }

        $lines = preg_split('/\r\n|\r|\n/', $text) ?: [];

        return array_values(array_filter(array_map('trim', $lines)));
    }

    /**
     * @return array<string, mixed>
     */
    private function builtinDefaults(): array
    {
        return [
            'agent_enabled' => true,
            'sandbox_enabled' => false,
            'sandbox_image' => 'ai-dev-agent-sandbox:latest',
            'sandbox_network' => 'none',
            'require_approval_before_pr' => false,
            'max_retries' => 3,
            'max_runtime_minutes' => 120,
            'max_tokens_per_task' => 500_000,
            'risk_threshold' => 'medium',
            'allowed_repositories' => [],
            'blocked_file_patterns' => [],
            'blocked_command_patterns' => [],
            'allowed_command_prefixes' => [],
        ];
    }

    private function projectDefaultsPath(): string
    {
        return rtrim((string) config('ai_agent.project_path'), '/').'/hardening.defaults.json';
    }

    private function storagePath(): string
    {
        return storage_path(self::STORAGE_FILE);
    }
}
