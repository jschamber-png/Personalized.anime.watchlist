# Personalized Anime Watchlist

This repository publishes one RSS digest for the week's anime airtimes. The
publisher adds the digest 24 hours before the first listed episode. IFTTT can
then post that new feed item to Discord.

## Setup

1. Commit and push the repository to GitHub.
2. In **Settings > Pages**, set the source to **GitHub Actions**.
3. In **Settings > Actions > General**, set workflow permissions to **Read and
	write permissions** and allow GitHub Actions to create pull requests. The
	publisher needs to commit the generated feed to the default branch.
4. Add an Actions repository secret named `OPENAI_API_KEY`. OpenAI API usage
	is billed separately from a ChatGPT subscription.
5. Run **Actions > Publish anime digest > Run workflow** once to publish the
	initial empty feed and verify the Pages deployment.
6. Set IFTTT's RSS trigger URL to
	`https://jschamber-png.github.io/Personalized.anime.watchlist/anime-schedule.xml`.

The repository must be public for a public GitHub Pages feed on plans that do
not support public Pages from private repositories. Making the repository
public exposes all of its files, not just the feed.

## Weekly updates

The **Refresh anime schedule** workflow runs Fridays and uses the OpenAI API's
web search to propose next week's airtimes for the shows in `watchlist.json`.
It opens a pull request with the proposed `schedule.json`; review the source
links and merge it before the first airing's 24-hour deadline. The publisher
checks every 15 minutes and publishes one digest item when that deadline is
reached. GitHub Actions and IFTTT polling can add delivery delay.

The schedule uses `America/Chicago` and records each airing with its UTC
offset. The generated feed is `docs/anime-schedule.xml`. The schedule refresh
does not invent times when it cannot find a reliable source; review its pull
request before merging.

To test locally, run:

```sh
python -m unittest discover -s tests
python scripts/publish_digest.py
```
