<?php

namespace App\Providers;

use App\Services\AiAgentHealthService;
use Illuminate\Support\Facades\View;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        View::composer('layouts.ai-agent', function ($view) {
            if (! $view->offsetExists('health')) {
                $view->with('health', app(AiAgentHealthService::class)->check());
            }
        });
    }
}
