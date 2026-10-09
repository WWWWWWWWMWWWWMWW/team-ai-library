#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

function usage() {
  console.error("Usage: node verify_badge_assets.mjs <mergeclient-repo> <badgeRes...>");
  console.error("Example: node verify_badge_assets.mjs /Users/me/Desktop/mergeclient Card2608 Card2608_1");
}

function readJson(file, errors) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    errors.push(`${file}: cannot parse JSON (${error.message})`);
    return null;
  }
}

function exists(file, errors) {
  if (!fs.existsSync(file)) {
    errors.push(`missing: ${file}`);
    return false;
  }
  return true;
}

function loadLibraryMap(repoRoot) {
  const file = path.join(repoRoot, "client/library/uuid-to-mtime.json");
  if (!fs.existsSync(file)) return null;
  const json = JSON.parse(fs.readFileSync(file, "utf8"));
  const byPath = new Map();
  for (const [uuid, value] of Object.entries(json)) {
    if (value && value.relativePath) byPath.set(value.relativePath, uuid);
  }
  return byPath;
}

function checkLibrary(byPath, relPath, expectedUuid, errors, warnings) {
  if (!byPath) return;
  const libraryUuid = byPath.get(relPath);
  if (!libraryUuid) {
    warnings.push(`library has no path yet: ${relPath}`);
    return;
  }
  if (libraryUuid !== expectedUuid) {
    errors.push(`library uuid mismatch: ${relPath} meta=${expectedUuid} library=${libraryUuid}`);
  }
}

function checkBadge(repoRoot, badgeRes, byPath) {
  const errors = [];
  const warnings = [];
  const iconRel = `client/assets/remoteAsset/Texture/Badge/icon_Badge_${badgeRes}.png`;
  const iconMetaRel = `${iconRel}.meta`;
  const spineName = `Badge${badgeRes}`;
  const spineBaseRel = `client/assets/spineAsset/Spine/Badge/${spineName}`;

  for (const rel of [
    iconRel,
    iconMetaRel,
    `${spineBaseRel}.atlas`,
    `${spineBaseRel}.atlas.meta`,
    `${spineBaseRel}.png`,
    `${spineBaseRel}.png.meta`,
    `${spineBaseRel}.skel`,
    `${spineBaseRel}.skel.meta`,
  ]) {
    exists(path.join(repoRoot, rel), errors);
  }

  if (errors.length) return { badgeRes, errors, warnings };

  const iconMeta = readJson(path.join(repoRoot, iconMetaRel), errors);
  const spinePngMeta = readJson(path.join(repoRoot, `${spineBaseRel}.png.meta`), errors);
  const spineSkelMeta = readJson(path.join(repoRoot, `${spineBaseRel}.skel.meta`), errors);
  const atlasMeta = readJson(path.join(repoRoot, `${spineBaseRel}.atlas.meta`), errors);
  const atlasText = fs.readFileSync(path.join(repoRoot, `${spineBaseRel}.atlas`), "utf8");

  if (!iconMeta || !spinePngMeta || !spineSkelMeta || !atlasMeta) {
    return { badgeRes, errors, warnings };
  }

  const iconSub = iconMeta.subMetas && iconMeta.subMetas[`icon_Badge_${badgeRes}`];
  if (!iconSub) {
    errors.push(`missing icon subMeta: icon_Badge_${badgeRes}`);
  } else if (iconSub.rawTextureUuid !== iconMeta.uuid) {
    errors.push(`icon rawTextureUuid mismatch: ${badgeRes}`);
  }

  const spineSub = spinePngMeta.subMetas && spinePngMeta.subMetas[spineName];
  if (!spineSub) {
    errors.push(`missing spine png subMeta: ${spineName}`);
  } else if (spineSub.rawTextureUuid !== spinePngMeta.uuid) {
    errors.push(`spine png rawTextureUuid mismatch: ${spineName}`);
  }

  if (!Array.isArray(spineSkelMeta.textures) || spineSkelMeta.textures[0] !== spinePngMeta.uuid) {
    errors.push(`spine skel texture uuid mismatch: ${spineName}`);
  }

  if (!atlasText.includes(`${spineName}.png`)) {
    errors.push(`atlas does not reference ${spineName}.png`);
  }

  checkLibrary(byPath, `remoteAsset/Texture/Badge/icon_Badge_${badgeRes}.png`, iconMeta.uuid, errors, warnings);
  checkLibrary(byPath, `spineAsset/Spine/Badge/${spineName}.atlas`, atlasMeta.uuid, errors, warnings);
  checkLibrary(byPath, `spineAsset/Spine/Badge/${spineName}.png`, spinePngMeta.uuid, errors, warnings);
  checkLibrary(byPath, `spineAsset/Spine/Badge/${spineName}.skel`, spineSkelMeta.uuid, errors, warnings);

  return { badgeRes, errors, warnings };
}

function main() {
  const [repoRoot, ...badgeResList] = process.argv.slice(2);
  if (!repoRoot || badgeResList.length === 0) {
    usage();
    process.exit(2);
  }

  const absRepo = path.resolve(repoRoot);
  if (!fs.existsSync(path.join(absRepo, "client/assets"))) {
    console.error(`Not a mergeclient repo or missing client/assets: ${absRepo}`);
    process.exit(2);
  }

  const byPath = loadLibraryMap(absRepo);
  const results = badgeResList.map((badgeRes) => checkBadge(absRepo, badgeRes, byPath));
  let failed = false;
  for (const result of results) {
    if (result.errors.length) failed = true;
    console.log(`${result.badgeRes}: ${result.errors.length ? "FAIL" : "OK"}`);
    for (const warning of result.warnings) console.log(`  warning: ${warning}`);
    for (const error of result.errors) console.log(`  error: ${error}`);
  }
  process.exit(failed ? 1 : 0);
}

main();
