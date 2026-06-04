<?php

use App\Http\Controllers\AiAgentActionController;
use App\Http\Controllers\AiAgentBatchController;
use App\Http\Controllers\AiAgentTaskController;
use Illuminate\Support\Facades\Route;

Route::redirect('/', '/ai-agent/tasks');

Route::prefix('ai-agent')->name('ai-agent.')->group(function () {
    Route::post('jira-batch/run', [AiAgentBatchController::class, 'runJiraBatch'])
        ->name('jira-batch.run');

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
});
