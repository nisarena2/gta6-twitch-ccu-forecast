[![competition](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/nisarena2/gta6-twitch-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/nisarena2/gta6-twitch-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

# GTA VI Twitch viewers — launch-day forecast

Forecasts how many people watch Grand Theft Auto VI live on Twitch in
each hour of its release day (19 November 2026, UTC), from everything
recorded up to the end of the day's first hour, as five quantiles an
hour (5%, 25%, 50%, 75%, 95%).

## How it works

For every past big launch in the case's comparables, the release-day
hourly viewers are divided by that launch's hour-1 print, giving a
ratio curve. Across launches, the log of the ratio for each hour is
regressed on the log of the hour-1 print: big launches grow less, in
ratio terms, than small ones, because their first hour already holds
most of the world that has unlocked. The fitted line at this case's
hour-1 print is the median ratio, and the spread is a robust (MAD)
residual scale, so the few launches whose first hour fell before their
unlock do not blow the intervals up. The slope is capped at -0.5 so the
forecast stays sensible when the hour-1 print is larger than any
comparable's. The GTA VI category's own pre-release curve is a trailer
premiere, not a launch day, so it is left out of the fit.

On the four practice launches this scores a mean pinball loss of
0.197, against the house baseline's 0.387.

## Running it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `*.in` file in the input directory and writes one
`<id>.out` file per case to the output directory. Standard library
only, no network, deterministic: two runs on the same case write
byte-identical output.

## License

MIT — see [LICENSE](LICENSE).
