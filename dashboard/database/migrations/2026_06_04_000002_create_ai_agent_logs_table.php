<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ai_agent_logs', function (Blueprint $table) {
            $table->id();
            $table->foreignId('ai_agent_task_id')->constrained()->cascadeOnDelete();
            $table->string('level')->default('info');
            $table->string('step')->nullable();
            $table->text('message');
            $table->json('context')->nullable();
            $table->timestamp('created_at')->useCurrent();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ai_agent_logs');
    }
};
