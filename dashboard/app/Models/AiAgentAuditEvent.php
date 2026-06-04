<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class AiAgentAuditEvent extends Model
{
    public $timestamps = false;

    protected $fillable = [
        'ai_agent_task_id',
        'event',
        'level',
        'detail',
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
