<?php

namespace App\Models;

use App\Enums\AiAgentTaskStatus;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class AiAgentTask extends Model
{
    protected $fillable = [
        'jira_issue_key',
        'jira_summary',
        'jira_url',
        'repo_path',
        'repo_url',
        'branch_name',
        'task_description',
        'status',
        'risk_level',
        'validation_status',
        'pr_url',
        'pr_number',
        'logs_path',
        'error_message',
        'changed_files',
        'started_at',
        'completed_at',
    ];

    protected function casts(): array
    {
        return [
            'status' => AiAgentTaskStatus::class,
            'changed_files' => 'array',
            'started_at' => 'datetime',
            'completed_at' => 'datetime',
        ];
    }

    public function logs(): HasMany
    {
        return $this->hasMany(AiAgentLog::class)->orderBy('id');
    }

    public function isHighRisk(): bool
    {
        if ($this->risk_level === 'high') {
            return true;
        }

        $text = strtolower($this->task_description.' '.($this->jira_summary ?? ''));
        foreach (config('ai_agent.high_risk_keywords', []) as $keyword) {
            if (str_contains($text, $keyword)) {
                return true;
            }
        }

        return false;
    }

    public function requiresApprovalBeforeRun(): bool
    {
        if (! config('ai_agent.requires_approval')) {
            return false;
        }

        return in_array($this->status, [
            AiAgentTaskStatus::Pending,
        ], true);
    }

    public function canRun(): bool
    {
        if (in_array($this->status, [
            AiAgentTaskStatus::Rejected,
            AiAgentTaskStatus::Running,
        ], true)) {
            return false;
        }

        if ($this->isHighRisk() && $this->status !== AiAgentTaskStatus::Approved) {
            return false;
        }

        if ($this->requiresApprovalBeforeRun()) {
            return false;
        }

        return in_array($this->status, [
            AiAgentTaskStatus::Pending,
            AiAgentTaskStatus::Approved,
            AiAgentTaskStatus::Failed,
            AiAgentTaskStatus::TestsFailed,
        ], true);
    }

    public function needsManualApproval(): bool
    {
        if ($this->status !== AiAgentTaskStatus::Pending) {
            return false;
        }

        return $this->isHighRisk() || config('ai_agent.requires_approval');
    }
}
