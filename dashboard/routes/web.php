<?php

use App\Http\Controllers\AiAgentActionController;
use App\Http\Controllers\AiAgentBatchController;
use App\Http\Controllers\AiAgentDashboardController;
use App\Http\Controllers\AiAgentPipelineController;
use App\Http\Controllers\AiAgentSettingsController;
use App\Http\Controllers\AiAgentTaskController;
use Illuminate\Support\Facades\Route;

Route::redirect('/', '/ai-agent');

Route::prefix('ai-agent')->name('ai-agent.')->group(function () {
    Route::get('/', [AiAgentDashboardController::class, 'index'])->name('dashboard');
    Route::get('settings', [AiAgentSettingsController::class, 'index'])->name('settings');

    Route::post('jira-batch/run', [AiAgentBatchController::class, 'runJiraBatch'])
        ->name('jira-batch.run');

    Route::get('pipeline/sync', [AiAgentPipelineController::class, 'sync'])
        ->name('pipeline.sync');
    Route::get('tasks/{task}/pipeline', [AiAgentPipelineController::class, 'show'])
        ->name('tasks.pipeline');

    Route::get('tasks', [AiAgentTaskController::class, 'index'])->name('tasks.index');
    Route::get('tasks/{task}', [AiAgentTaskController::class, 'show'])->name('tasks.show');

    Route::post('tasks/{task}/approve', [AiAgentActionController::class, 'approve'])
        ->name('tasks.approve');
    Route::post('tasks/{task}/reject', [AiAgentActionController::class, 'reject'])
        ->name('tasks.reject');
    Route::post('tasks/{task}/retry', [AiAgentActionController::class, 'retry'])
        ->name('tasks.retry');
    Route::post('tasks/{task}/run', [AiAgentActionController::class, 'run'])
        ->name('tasks.run');
    Route::post('tasks/{task}/stop', [AiAgentActionController::class, 'stop'])
        ->name('tasks.stop');
});
