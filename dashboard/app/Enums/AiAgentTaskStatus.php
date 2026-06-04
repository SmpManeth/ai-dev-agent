<?php

namespace App\Enums;

enum AiAgentTaskStatus: string
{
    case Pending = 'pending';
    case Approved = 'approved';
    case Running = 'running';
    case PatchGenerated = 'patch_generated';
    case PatchApplied = 'patch_applied';
    case TestsRunning = 'tests_running';
    case TestsPassed = 'tests_passed';
    case TestsFailed = 'tests_failed';
    case Committed = 'committed';
    case PrCreated = 'pr_created';
    case JiraUpdated = 'jira_updated';
    case Completed = 'completed';
    case Failed = 'failed';
    case Skipped = 'skipped';
    case Rejected = 'rejected';
    case Queued = 'queued';

    public function label(): string
    {
        return str_replace('_', ' ', $this->value);
    }

    public function badgeColor(): string
    {
        return match ($this) {
            self::Pending => 'bg-amber-100 text-amber-800',
            self::Approved => 'bg-blue-100 text-blue-800',
            self::Running, self::TestsRunning => 'bg-indigo-100 text-indigo-800',
            self::TestsPassed, self::Completed, self::PrCreated, self::JiraUpdated => 'bg-green-100 text-green-800',
            self::TestsFailed, self::Failed => 'bg-red-100 text-red-800',
            self::Rejected, self::Skipped => 'bg-gray-200 text-gray-700',
            self::Queued => 'bg-amber-50 text-amber-700',
            default => 'bg-slate-100 text-slate-800',
        };
    }
}
