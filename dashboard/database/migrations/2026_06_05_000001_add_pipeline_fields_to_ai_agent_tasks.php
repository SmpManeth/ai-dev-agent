<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('ai_agent_tasks', function (Blueprint $table) {
            $table->string('pipeline_phase')->default('not_started')->index()->after('status');
            $table->string('pipeline_label')->nullable()->after('pipeline_phase');
            $table->unsignedTinyInteger('pipeline_percent')->default(0)->after('pipeline_label');
            $table->unsignedTinyInteger('pipeline_step')->default(0)->after('pipeline_percent');
            $table->unsignedTinyInteger('pipeline_step_total')->default(9)->after('pipeline_step');
            $table->boolean('pipeline_terminal')->default(false)->after('pipeline_step_total');
            $table->json('pipeline_history')->nullable()->after('pipeline_terminal');
            $table->timestamp('pipeline_updated_at')->nullable()->after('pipeline_history');
        });
    }

    public function down(): void
    {
        Schema::table('ai_agent_tasks', function (Blueprint $table) {
            $table->dropColumn([
                'pipeline_phase',
                'pipeline_label',
                'pipeline_percent',
                'pipeline_step',
                'pipeline_step_total',
                'pipeline_terminal',
                'pipeline_history',
                'pipeline_updated_at',
            ]);
        });
    }
};
