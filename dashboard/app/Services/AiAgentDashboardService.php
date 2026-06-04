<?php

namespace App\Services;

use App\Enums\AiAgentTaskStatus;
use App\Models\AiAgentTask;
use Illuminate\Support\Carbon;

class AiAgentDashboardService
{
    public function __construct(
        private readonly AiAgentBatchService $batchService,
        private readonly AiAgentHealthService $healthService,
    ) {}

    /**
     * @return array<string, mixed>
     */
    public function overview(): array
    {
        $statusCounts = [];
        foreach (AiAgentTaskStatus::cases() as $status) {
            $statusCounts[$status->value] = AiAgentTask::query()
                ->where('status', $status->value)
                ->count();
        }

        $recent = AiAgentTask::query()
            ->latest('updated_at')
            ->limit(8)
            ->get();

        $prCreated = AiAgentTask::query()
            ->whereIn('status', [
                AiAgentTaskStatus::PrCreated,
                AiAgentTaskStatus::JiraUpdated,
                AiAgentTaskStatus::Completed,
            ])
            ->count();

        $failed = AiAgentTask::query()
            ->whereIn('status', [
                AiAgentTaskStatus::Failed,
                AiAgentTaskStatus::TestsFailed,
            ])
            ->count();

        return [
            'total_tasks' => AiAgentTask::query()->count(),
            'pr_created' => $prCreated,
            'failed' => $failed,
            'pending_review' => AiAgentTask::query()
                ->whereIn('status', [AiAgentTaskStatus::Pending, AiAgentTaskStatus::Approved])
                ->count(),
            'status_counts' => $statusCounts,
            'recent_tasks' => $recent,
            'scheduler' => $this->batchService->getSchedulerState(),
            'health' => $this->healthService->check(),
            'last_activity' => AiAgentTask::query()->max('updated_at'),
        ];
    }

    public function lastActivityHuman(): ?string
    {
        $raw = AiAgentTask::query()->max('updated_at');
        if (! $raw) {
            return null;
        }

        return Carbon::parse($raw)->diffForHumans();
    }
}
