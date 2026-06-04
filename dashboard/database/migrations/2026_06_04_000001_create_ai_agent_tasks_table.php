<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('ai_agent_tasks', function (Blueprint $table) {
            $table->id();
            $table->string('jira_issue_key')->nullable()->index();
            $table->string('jira_summary')->nullable();
            $table->string('jira_url')->nullable();
            $table->string('repo_path');
            $table->string('repo_url')->nullable();
            $table->string('branch_name')->nullable();
            $table->text('task_description');
            $table->string('status')->default('pending')->index();
            $table->string('risk_level')->nullable();
            $table->string('validation_status')->nullable();
            $table->string('pr_url')->nullable();
            $table->unsignedInteger('pr_number')->nullable();
            $table->string('logs_path')->nullable();
            $table->text('error_message')->nullable();
            $table->json('changed_files')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('completed_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('ai_agent_tasks');
    }
};
