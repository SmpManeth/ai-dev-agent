<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class AiAgentLog extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'ai_agent_task_id',
        'level',
        'step',
        'message',
        'context',
        'created_at',
    ];

    protected function casts(): array
    {
        return [
            'context' => 'array',
            'created_at' => 'datetime',
        ];
    }

    public function task(): BelongsTo
    {
        return $this->belongsTo(AiAgentTask::class, 'ai_agent_task_id');
    }
}
