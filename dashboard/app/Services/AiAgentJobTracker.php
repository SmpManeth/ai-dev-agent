<?php

namespace App\Services;

use Illuminate\Support\Facades\File;
use Symfony\Component\Process\Process;

class AiAgentJobTracker
{
    private const JOBS_DIR = 'app/agent-jobs';

    /**
     * @param  array<string, mixed>  $meta
     */
    public function register(string $jobId, int $pid, array $meta): void
    {
        $dir = storage_path(self::JOBS_DIR);
        File::ensureDirectoryExists($dir);

        File::put($dir.'/'.$jobId.'.json', json_encode(array_merge($meta, [
            'job_id' => $jobId,
            'pid' => $pid,
            'registered_at' => now()->toIso8601String(),
        ]), JSON_PRETTY_PRINT));
    }

    public function remove(string $jobId): void
    {
        $path = $this->pathFor($jobId);
        if (File::exists($path)) {
            File::delete($path);
        }
    }

    /**
     * @return list<array<string, mixed>>
     */
    public function activeJobs(): array
    {
        $dir = storage_path(self::JOBS_DIR);
        if (! is_dir($dir)) {
            return [];
        }

        $jobs = [];
        foreach (File::files($dir) as $file) {
            if ($file->getExtension() !== 'json') {
                continue;
            }
            $data = json_decode(File::get($file->getPathname()), true);
            if (is_array($data)) {
                $jobs[] = $data;
            }
        }

        return $jobs;
    }

    public function isPidRunning(int $pid): bool
    {
        if ($pid <= 0) {
            return false;
        }

        if (function_exists('posix_kill')) {
            return @posix_kill($pid, 0);
        }

        $process = Process::fromShellCommandline('kill -0 '.$pid.' 2>/dev/null');
        $process->run();

        return $process->isSuccessful();
    }

    private function pathFor(string $jobId): string
    {
        return storage_path(self::JOBS_DIR.'/'.preg_replace('/[^a-zA-Z0-9._-]/', '_', $jobId).'.json');
    }
}
