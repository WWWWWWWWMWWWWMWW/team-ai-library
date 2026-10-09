#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

function fail(message) {
  throw new Error(message);
}

function assert(condition, message) {
  if (!condition) fail(message);
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) fail(`unexpected argument: ${token}`);
    const key = token.slice(2);
    if (["assets", "require-all-art"].includes(key)) {
      args[key] = true;
      continue;
    }
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) fail(`missing value for --${key}`);
    args[key] = value;
    index += 1;
  }
  return args;
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]));
  }
  return value;
}

function same(left, right) {
  return JSON.stringify(stable(left)) === JSON.stringify(stable(right));
}

function gitHeadJson(repo, relativePath) {
  try {
    const content = execFileSync("git", ["show", `HEAD:${relativePath}`], {
      cwd: repo,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    return JSON.parse(content);
  } catch {
    return null;
  }
}

function assertOldArrayUnchanged(name, baseline, current, idKey = "id") {
  if (!baseline) return;
  for (const oldItem of baseline) {
    const currentItem = current.find((item) => item[idKey] === oldItem[idKey]);
    assert(currentItem, `${name}: old ${idKey}=${oldItem[idKey]} is missing`);
    assert(same(oldItem, currentItem), `${name}: old ${idKey}=${oldItem[idKey]} changed`);
  }
}

function assertOldSheetsUnchanged(name, baseline, current, targetKey) {
  if (!baseline) return;
  for (const [key, oldSheet] of Object.entries(baseline)) {
    if (key === targetKey) continue;
    assert(key in current, `${name}: old sheet ${key} is missing`);
    assert(same(oldSheet, current[key]), `${name}: old sheet ${key} changed`);
  }
}

function pngSize(file) {
  const data = fs.readFileSync(file);
  assert(data.length >= 24 && data.toString("ascii", 1, 4) === "PNG", `${file}: invalid PNG`);
  return { width: data.readUInt32BE(16), height: data.readUInt32BE(20) };
}

function sha256(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function seasonSuffix(season) {
  return season[0].toUpperCase() + season.slice(1);
}

const args = parseArgs(process.argv.slice(2));
for (const key of ["repo", "region", "season", "previous", "series-start", "card-start", "series-count", "cards-per-series", "gold-count"]) {
  assert(args[key] !== undefined, `required argument missing: --${key}`);
}

const repo = path.resolve(args.repo);
const region = args.region;
const season = args.season;
const previous = args.previous;
const seriesStart = Number(args["series-start"]);
const cardStart = Number(args["card-start"]);
const seriesCount = Number(args["series-count"]);
const cardsPerSeries = Number(args["cards-per-series"]);
const goldCount = Number(args["gold-count"]);
for (const [name, value] of Object.entries({ seriesStart, cardStart, seriesCount, cardsPerSeries, goldCount })) {
  assert(Number.isInteger(value), `${name} must be an integer`);
}

const jsonRelativeRoot = `server/config/json_${region}`;
const jsonRoot = path.join(repo, jsonRelativeRoot);
const load = (name, rootKey) => {
  const file = path.join(jsonRoot, name);
  assert(fs.existsSync(file), `missing ${file}`);
  const value = readJson(file)[rootKey];
  assert(value !== undefined, `${name}: missing root key ${rootKey}`);
  return value;
};
const headLoad = (name, rootKey) => gitHeadJson(repo, `${jsonRelativeRoot}/${name}`)?.[rootKey] ?? null;

const activities = load("seasonCardActivity.json", "seasonCardActivity");
const cardsBySeason = load("seasonCardCard.json", "seasonCardCard");
const seriesBySeason = load("seasonCardSeries.json", "seasonCardSeries");
const mails = load("seasonCardMail.json", "seasonCardMail");
const packs = load("seasonCardPack.json", "seasonCardPack");
const badges = load("badgeList.json", "badgeList");

const suffix = seasonSuffix(season);
const previousSuffix = seasonSuffix(previous);
const cardKey = `seasonCardCard${suffix}`;
const previousCardKey = `seasonCardCard${previousSuffix}`;
const seriesKey = `seasonCardSeries${suffix}`;
const previousSeriesKey = `seasonCardSeries${previousSuffix}`;
const activity = activities.find((item) => item.id === season);
const previousActivity = activities.find((item) => item.id === previous);
const cards = cardsBySeason[cardKey];
const previousCards = cardsBySeason[previousCardKey];
const series = seriesBySeason[seriesKey];
const previousSeries = seriesBySeason[previousSeriesKey];

assert(activity, `missing activity ${season}`);
assert(previousActivity, `missing previous activity ${previous}`);
assert(Array.isArray(cards), `missing card sheet ${cardKey}`);
assert(Array.isArray(previousCards), `missing previous card sheet ${previousCardKey}`);
assert(Array.isArray(series), `missing series sheet ${seriesKey}`);
assert(Array.isArray(previousSeries), `missing previous series sheet ${previousSeriesKey}`);

assert(cards.length === seriesCount * cardsPerSeries, `expected ${seriesCount * cardsPerSeries} cards, got ${cards.length}`);
assert(series.length === seriesCount, `expected ${seriesCount} series, got ${series.length}`);
assert(new Set(cards.map((item) => item.id)).size === cards.length, "duplicate card ids");
assert(new Set(series.map((item) => item.id)).size === series.length, "duplicate series ids");
assert(new Set(cards.map((item) => item.cardName)).size === cards.length, "duplicate card names");
assert(new Set(series.map((item) => item.seriesName)).size === series.length, "duplicate series names");
assert(cards.every((item) => item.cardName && !/待补|占位|TBD|TODO|未定/i.test(item.cardName)), "empty or placeholder card name remains");
assert(series.every((item) => item.seriesName && !/待补|占位|TBD|TODO|未定/i.test(item.seriesName)), "empty or placeholder series name remains");

for (let index = 0; index < cards.length; index += 1) {
  const card = cards[index];
  assert(card.id === cardStart + index, `card id mismatch at index ${index}: ${card.id}`);
  assert(card.seriesId === seriesStart + Math.floor(index / cardsPerSeries), `card ${card.id}: seriesId mismatch`);
  assert(Number(card.cardRes) === (index % cardsPerSeries) + 1, `card ${card.id}: cardRes mismatch`);
  if (previousCards.length === cards.length) {
    for (const field of ["star", "isGolden", "weight", "newweight"]) {
      assert(card[field] === previousCards[index][field], `card ${card.id}: ${field} drifted from ${previous}`);
    }
  }
}
assert(cards.filter((item) => item.isGolden === 1).length === goldCount, `expected ${goldCount} gold cards`);

for (let index = 0; index < series.length; index += 1) {
  const item = series[index];
  assert(item.id === seriesStart + index, `series id mismatch at index ${index}: ${item.id}`);
  assert(Number(item.seriesRes) === index + 1, `series ${item.id}: seriesRes mismatch`);
  assert(cards.filter((card) => card.seriesId === item.id).length === cardsPerSeries, `series ${item.id}: card count mismatch`);
  if (previousSeries.length === series.length) {
    assert(same(item.reward, previousSeries[index].reward), `series ${item.id}: reward drifted from ${previous}`);
  }
}

const rewardBadgeIds = [];
for (const reward of [activity.firstReward, activity.secondReward]) {
  for (const key of Object.keys(reward || {})) {
    const match = /^Badge(\d+)$/.exec(key);
    if (match) rewardBadgeIds.push(Number(match[1]));
  }
}
assert(rewardBadgeIds.length > 0, `${season}: no badge reward found`);
const seasonBadges = rewardBadgeIds.map((id) => {
  const badge = badges.find((item) => item.badgeID === id);
  assert(badge, `missing badgeList row ${id}`);
  assert(badge.actType === `cardSeason_${season}`, `badge ${id}: actType mismatch`);
  assert(badge.badgeRes, `badge ${id}: badgeRes is empty`);
  return badge;
});

const mail = mails.find((item) => item.id === activity.passRewardMailID);
assert(mail, `missing pass reward mail ${activity.passRewardMailID}`);
assert(mail.belong === season, `mail ${mail.id}: belong=${mail.belong}, expected ${season}`);

assertOldArrayUnchanged("activity", headLoad("seasonCardActivity.json", "seasonCardActivity"), activities);
assertOldSheetsUnchanged("cards", headLoad("seasonCardCard.json", "seasonCardCard"), cardsBySeason, cardKey);
assertOldSheetsUnchanged("series", headLoad("seasonCardSeries.json", "seasonCardSeries"), seriesBySeason, seriesKey);
assertOldArrayUnchanged("mail", headLoad("seasonCardMail.json", "seasonCardMail"), mails);
assertOldArrayUnchanged("badge", headLoad("badgeList.json", "badgeList"), badges, "badgeID");
const headPacks = headLoad("seasonCardPack.json", "seasonCardPack");
assert(!headPacks || same(headPacks, packs), "seasonCardPack changed from HEAD");

const goConfigFile = path.join(repo, "server/config/config.go");
const configTsFile = path.join(repo, "client/assets/Script/game/common/config/Config.ts");
assert(fs.existsSync(goConfigFile), "missing server/config/config.go");
assert(fs.existsSync(configTsFile), "missing client Config.ts");
const goConfig = fs.readFileSync(goConfigFile, "utf8");
const configTs = fs.readFileSync(configTsFile, "utf8");
assert(goConfig.includes("func _GetConfig() *config_"), "server config.go: _GetConfig is missing");
assert(!goConfig.includes("func GetConfig() *config_"), "server config.go: incompatible GetConfig remains");
assert(goConfig.includes(`SeasonCardCardSheetList["${season}"]`), `Go card map lacks ${season}`);
assert(goConfig.includes(`SeasonCardSeriesSheetList["${season}"]`), `Go series map lacks ${season}`);
assert(configTs.includes(`"${season}"`), `client Config.ts lacks ${season}`);

const missingArt = [];
const assetChecks = [];
if (args.assets) {
  const assetRoot = path.join(repo, `client/assets/remoteAsset/Texture/CardsSeason/${season}`);
  for (let seriesIndex = 1; seriesIndex <= seriesCount; seriesIndex += 1) {
    for (let cardIndex = 1; cardIndex <= cardsPerSeries; cardIndex += 1) {
      const file = path.join(assetRoot, "Cards", String(seriesIndex), `${cardIndex}.png`);
      assert(fs.existsSync(file), `missing card art ${seriesIndex}/${cardIndex}.png`);
      assert(same(pngSize(file), { width: 370, height: 370 }), `wrong card art size ${seriesIndex}/${cardIndex}.png`);
      assert(fs.existsSync(`${file}.meta`), `missing card meta ${seriesIndex}/${cardIndex}.png.meta`);
      assetChecks.push(file);
    }
    const entrance = path.join(assetRoot, "Series/Entrance", `${seriesIndex}.png`);
    assert(fs.existsSync(entrance), `missing entrance art ${seriesIndex}.png`);
    assert(same(pngSize(entrance), { width: 200, height: 200 }), `wrong entrance size ${seriesIndex}.png`);
    assert(fs.existsSync(`${entrance}.meta`), `missing entrance meta ${seriesIndex}.png.meta`);
    assetChecks.push(entrance);
  }

  for (const name of ["img_ui_bg.png", "img_notice.png", "img_ending.png"]) {
    const file = path.join(assetRoot, name);
    if (!fs.existsSync(file)) missingArt.push(path.relative(repo, file));
  }

  for (const badge of seasonBadges) {
    const icon = path.join(repo, `client/assets/remoteAsset/Texture/Badge/icon_Badge_${badge.badgeRes}.png`);
    const spineRoot = path.join(repo, `client/assets/spineAsset/Spine/Badge/Badge${badge.badgeRes}`);
    for (const file of [icon, `${icon}.meta`, `${spineRoot}.atlas`, `${spineRoot}.png`, `${spineRoot}.skel`]) {
      assert(fs.existsSync(file), `missing badge asset ${path.relative(repo, file)}`);
    }
    assert(same(pngSize(icon), { width: 128, height: 128 }), `badge ${badge.badgeID}: icon must be 128x128`);
  }

  const uuids = [];
  for (const file of assetChecks) {
    const meta = readJson(`${file}.meta`);
    assert(meta.uuid, `${file}.meta: uuid missing`);
    uuids.push(meta.uuid);
  }
  assert(new Set(uuids).size === uuids.length, "duplicate target-season image UUIDs");
}

if (args["require-all-art"]) {
  assert(args.assets, "--require-all-art requires --assets");
  assert(missingArt.length === 0, `missing final art: ${missingArt.join(", ")}`);
}

console.log(JSON.stringify({
  passed: true,
  repo,
  region,
  season,
  previous,
  theme: activity.themeName,
  seriesCount: series.length,
  cardCount: cards.length,
  goldCardCount: cards.filter((item) => item.isGolden === 1).length,
  badgeIds: seasonBadges.map((item) => item.badgeID),
  badgeResources: seasonBadges.map((item) => item.badgeRes),
  protectedSeasonCardPackSha256: sha256(path.join(jsonRoot, "seasonCardPack.json")),
  assetsChecked: Boolean(args.assets),
  missingArt,
  runtimeVerification: "required separately: build/restart, cardseason_tryinit, in-game open",
}, null, 2));
