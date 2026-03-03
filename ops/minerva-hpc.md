---
description: "Practical reference for Minerva HPC -- filesystem, LSF scheduler, queues, GPU jobs, modules, conda, and job templates"
type: "reference"
slug: "minerva-hpc"
created: "2026-03-03"
tags: [hpc, minerva, lsf, compute]
---

# Minerva HPC -- Practical Reference

Parent: [[mount-sinai]]

## Access

- Host: `minerva.hpc.mssm.edu`
- User: `chousa01`
- Auth: campus password + Symantec VIP MFA (new MFA onboarding required)
- Login nodes: `li04e01`, etc. -- DO NOT run production jobs here
- Support: hpchelp@hpc.mssm.edu
- Docs: https://labs.icahn.mssm.edu/minervalab/documentation/

## Filesystem

| Path | Env Var | Quota | Backup | Purge | Use |
|------|---------|-------|--------|-------|-----|
| `/hpc/users/chousa01` | `$HOME` | 20 GB | Yes | No | Config, small scripts, Rlibs |
| `/sc/arion/work/chousa01` | -- | 100 GB | No | No | Personal data, conda envs |
| `/sc/arion/scratch/chousa01` | -- | 10 TB | No | **14 days** | Temp computation output |
| `/sc/arion/projects/Chipuk_Laboratory` | -- | Custom | No | No | Lab shared storage |

- GPFS root: `/sc/arion` (env var `$GPFS`)
- Check quota: `showquota -u chousa01 arion` or `showquota -p Chipuk_Laboratory arion`
- **No automatic backups** -- archive important data to TSM or external
- Archival: IBM TSM (Tivoli), dual-copy tape, 6-year retention
- Transfer: Globus preferred (HIPAA-safe); SCP/SFTP for small files; no FTP

### Current layout (chousa01)

```
/hpc/users/chousa01/
  envs/            # environment configs
  Rlibs/           # R library installations
  ondemand/        # Open OnDemand config

/sc/arion/work/chousa01/
  conda/           # conda environments (keeps them off 20 GB home)

/sc/arion/projects/Chipuk_Laboratory/
  chousa01/        # personal project subdir
  *.csv            # shared DEG results, etc.
```

## LSF Scheduler

### Commands

| Command | Purpose |
|---------|---------|
| `bsub` | Submit job (batch or interactive) |
| `bjobs` | Check job status (`-u all` for all users) |
| `bkill <id>` | Kill job (`bkill 0` = kill all yours) |
| `bpeek <id>` | Peek at running job stdout |
| `bmod <id>` | Modify pending job |
| `bhist <id>` | Historical job info |
| `bqueues` | List available queues |
| `bhosts` | List compute nodes |

### Queues

| Queue | Max Walltime | Notes |
|-------|-------------|-------|
| `interactive` | 2h default, 12h max | Dev/debugging, 4 nodes + 1 GPU |
| `express` | 12h | Short serial/small jobs |
| `premium` | 6 days | Multi-core production runs |
| `long` | 2 weeks | Extended runs (limited: 4 nodes, 192 cores) |
| `gpu` | 6 days | GPU production |
| `gpuexpress` | shorter | Quick GPU jobs |
| `alloc` | varies | Jobs against PI allocation (`-P acc_<name>`) |

- Default memory: 3000 MB/core
- Walltime format: `HHH:MM` (no seconds)
- **Required flags**: `-P acc_<allocation>` and `-W <walltime>`
- **Default allocation**: `acc_Chipuk_Laboratory_Laboratory`
- **Default queue**: `premium`

## Job Templates

### Interactive session

```bash
bsub -P acc_Chipuk_Laboratory -q interactive -n 1 \
  -R rusage[mem=4000] -W 01:00 -Is /bin/bash
```

### Batch script (.lsf)

```bash
#!/bin/bash
#BSUB -J jobname
#BSUB -P acc_Chipuk_Laboratory
#BSUB -q premium
#BSUB -n 4
#BSUB -W 6:00
#BSUB -R rusage[mem=4000]
#BSUB -R "span[hosts=1]"
#BSUB -o %J.stdout
#BSUB -eo %J.stderr
#BSUB -L /bin/bash

module purge
module load python
# commands here
```

### GPU job (single GPU)

```bash
#!/bin/bash
#BSUB -J gpu-job
#BSUB -P acc_Chipuk_Laboratory
#BSUB -q gpu
#BSUB -n 1
#BSUB -W 6:00
#BSUB -R v100
#BSUB -R "rusage[ngpus_excl_p=1]"
#BSUB -R "span[hosts=1]"
#BSUB -R rusage[mem=8000]
#BSUB -o %J.stdout
#BSUB -eo %J.stderr
#BSUB -L /bin/bash

module purge
module load cuda
# GPU model options: v100, a100, h100nvl, l40s, b200
```

### Multi-GPU job

```bash
#BSUB -q gpu
#BSUB -n 8
#BSUB -R "span[ptile=2]"
#BSUB -R v100
#BSUB -R "rusage[ngpus_excl_p=2]"
```

### Array jobs

```bash
#BSUB -J "jobname[1-10]"
#BSUB -o logs/out.%J.%I
# Use $LSB_JOBINDEX for the array index
```

### Dependent jobs

```bash
bsub -J parent_job < job1.lsf
bsub -w 'done(parent_job)' < job2.lsf
```

### Self-scheduler (many short serial jobs < 10 min)

```bash
#BSUB -n 12
module load selfsched
mpirun -np 12 selfsched < input.inp
```

### OpenMP (shared memory)

```bash
#BSUB -n 4
#BSUB -R "span[hosts=1]"
#BSUB -R rusage[mem=12000]
export OMP_NUM_THREADS=4
```

## Module System (Lmod)

```bash
module avail              # list all modules
module spider R           # search for R versions
module load python        # load default
ml anaconda3/2020.11      # shorthand + specific version
ml purge                  # unload all
ml list                   # show loaded modules
```

## Conda

- Base: `ml anaconda3/<version>`
- Environments stored in `/sc/arion/work/chousa01/conda` (avoids home quota)
- Create: `conda create -p /sc/arion/work/chousa01/conda/<name> python=3.x`

## GPU Fleet

Current GPU types (check `gpuavail` on login node):

| Model | Queue | Notes |
|-------|-------|-------|
| B200 | gpu | 48 cards, 8x NVLink, 25 TB local NVME/node |
| H100 NVL | gpu, gpuexpress, private | 188 total |
| H100 80G | gpu, gpuexpress | 8 cards |
| A100 | gpu, gpuexpress | 40 cards |
| V100 | gpu, gpuexpress | 40 cards, 16/32 GB variants |
| L40S | gpu, gpuexpress | 32 cards |

Resource request syntax: `-R <model>` (e.g., `-R h100nvl`, `-R a100`)

## Hardware Summary

- 275 regular compute nodes (48 cores, 192 GB RAM each)
- 37 high-memory nodes (1.5 TB RAM)
- 32 PB total GPFS storage
- B200 nodes: 25 TB high-speed NVME local storage

## Best Practices

- Never run production jobs on login nodes
- Use scratch for intermediate output; results purged after 14 days
- Archive important results to projects dir or TSM before purge
- Use `span[hosts=1]` for shared-memory/OpenMP jobs
- Use self-scheduler for many short (<10 min) serial jobs
- Set `OMP_NUM_THREADS` explicitly for OpenMP jobs
- HIPAA agreement required annually (December deadline)
- Create conda envs on `/sc/arion/work/` not `$HOME`
