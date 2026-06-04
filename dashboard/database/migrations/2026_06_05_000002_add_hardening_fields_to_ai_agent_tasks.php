<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('ai_agent_tasks', function (Blueprint $table) {
            $table->unsignedInteger('token_count')->nullable()->after('error_message');
            $table->decimal('estimated_cost_usd', 10, 4)->nullable()->after('token_count');
        });

        Schema::create('ai_agent_audit_events', function (Blueprint $table) {
            $table->id();
            $table->foreignId('ai_agent_task_id')->nullable()->constrained()->nullOnDelete();
            $table->string('event', 64)->index();
            $table->string('level', 16)->default('info');
            $table->text('detail')->nullable();
            $table->json('context')->nullable();
            $table->timestamp('created_at')->useCurrent();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ai_agent_audit_events');

        Schema::table('ai_agent_tasks', function (Blueprint $table) {
            $table->dropColumn(['token_count', 'estimated_cost_usd']);
        });
    }
};
