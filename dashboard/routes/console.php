<?php

use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Schedule;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

/*
|--------------------------------------------------------------------------
| Automatic Jira polling (requires system cron: php artisan schedule:run)
|--------------------------------------------------------------------------
*/
$event = Schedule::command('ai-agent:run-jira-batch')
    ->when(fn () => (bool) config('ai_agent.schedule_enabled'))
    ->withoutOverlapping(config('ai_agent.schedule_overlap_minutes', 180))
    ->appendOutputTo(storage_path('logs/scheduler.log'));

$interval = max(1, (int) config('ai_agent.schedule_interval_minutes', 15));
match (true) {
    $interval === 1 => $event->everyMinute(),
    $interval === 5 => $event->everyFiveMinutes(),
    $interval === 10 => $event->everyTenMinutes(),
    $interval === 15 => $event->everyFifteenMinutes(),
    $interval === 30 => $event->everyThirtyMinutes(),
    $interval === 60 => $event->hourly(),
    default => $event->cron("*/{$interval} * * * *"),
};
