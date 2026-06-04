<?php

namespace App\Enums;

enum AiAgentPipelinePhase: string
{
    case NotStarted = 'not_started';
    case Queued = 'queued';
    case SyncingRepo = 'syncing_repo';
    case Planning = 'planning';
    case Researching = 'researching';
    case GeneratingPatch = 'generating_patch';
    case ValidatingPatch = 'validating_patch';
    case ApplyingPatch = 'applying_patch';
    case RunningTests = 'running_tests';
    case VerifyingFix = 'verifying_fix';
    case SelfFixing = 'self_fixing';
    case Committing = 'committing';
    case Pushing = 'pushing';
    case CreatingPr = 'creating_pr';
    case UpdatingJira = 'updating_jira';
    case Completed = 'completed';
    case Failed = 'failed';
    case Skipped = 'skipped';
    case WaitingApproval = 'waiting_approval';

    public function label(): string
    {
        return match ($this) {
            self::NotStarted => 'Not started',
            self::Queued => 'Queued',
            self::SyncingRepo => 'Syncing repository',
            self::Planning => 'Planning investigation',
            self::Researching => 'Researching root cause',
            self::GeneratingPatch => 'Generating patch',
            self::ValidatingPatch => 'Validating patch',
            self::ApplyingPatch => 'Applying patch',
            self::RunningTests => 'Running tests',
            self::VerifyingFix => 'Verifying fix',
            self::SelfFixing => 'Self-fixing',
            self::Committing => 'Committing changes',
            self::Pushing => 'Pushing to GitHub',
            self::CreatingPr => 'Creating pull request',
            self::UpdatingJira => 'Updating Jira',
            self::Completed => 'Completed',
            self::Failed => 'Failed',
            self::Skipped => 'Skipped',
            self::WaitingApproval => 'Waiting for approval',
        };
    }

    public function isActive(): bool
    {
        return ! $this->isTerminal() && $this !== self::NotStarted;
    }

    public function isTerminal(): bool
    {
        return in_array($this, [self::Completed, self::Failed, self::Skipped], true);
    }

    public function badgeColor(): string
    {
        return match ($this) {
            self::Completed => 'bg-emerald-100 text-emerald-800 ring-emerald-200',
            self::Failed => 'bg-red-100 text-red-800 ring-red-200',
            self::Skipped => 'bg-slate-100 text-slate-600 ring-slate-200',
            self::Queued, self::NotStarted => 'bg-slate-100 text-slate-600 ring-slate-200',
            self::WaitingApproval => 'bg-amber-100 text-amber-800 ring-amber-200',
            default => 'bg-blue-50 text-blue-800 ring-blue-200',
        };
    }

    public function badgeColorActive(): string
    {
        return match ($this) {
            self::Completed => $this->badgeColor(),
            self::Failed => $this->badgeColor(),
            self::Skipped => $this->badgeColor(),
            self::Queued, self::NotStarted => $this->badgeColor(),
            self::WaitingApproval => $this->badgeColor(),
            default => 'bg-blue-50 text-blue-800 ring-blue-200 animate-pulse',
        };
    }

    /**
     * @return list<array{phase: string, label: string}>
     */
    public static function stepDefinitions(): array
    {
        return [
            ['phase' => self::Planning->value, 'label' => 'Plan'],
            ['phase' => self::Researching->value, 'label' => 'Research'],
            ['phase' => self::GeneratingPatch->value, 'label' => 'Patch'],
            ['phase' => self::ApplyingPatch->value, 'label' => 'Apply'],
            ['phase' => self::RunningTests->value, 'label' => 'Test'],
            ['phase' => self::VerifyingFix->value, 'label' => 'Verify'],
            ['phase' => self::SelfFixing->value, 'label' => 'Retry'],
            ['phase' => self::Committing->value, 'label' => 'Commit'],
            ['phase' => self::CreatingPr->value, 'label' => 'PR'],
            ['phase' => self::UpdatingJira->value, 'label' => 'Jira'],
        ];
    }
}
