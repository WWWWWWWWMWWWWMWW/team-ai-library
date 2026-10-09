/* Optional browser acceptance: requires Playwright, a browser executable, and generated fixtures. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.TEAMLIB_PLAYWRIGHT || 'playwright');
const html=path.resolve(process.argv[2]);
const fixtures=path.resolve(process.argv[3]);
const output=path.resolve(process.argv[4]);
fs.mkdirSync(output,{recursive:true});
const checks=[];
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.TEAMLIB_BROWSER});
  const context=await browser.newContext({viewport:{width:1440,height:1000},offline:true,permissions:['clipboard-read','clipboard-write']});
  const page=await context.newPage(); const errors=[]; const network=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if (/^https?:/.test(r.url())) network.push(r.url())});
  const go=async file=>{await page.goto(pathToFileURL(file).href); await page.getByTestId('search').waitFor(); if(['local-library.html','standalone.html'].includes(path.basename(file))) await page.getByTestId('example-collection').click(); await page.locator('#advanced-filters').evaluate(el=>el.open=true);};
  const rows=()=>page.getByTestId('capability-row');
  const check=async(name,run)=>{await run(); checks.push(name); console.log('PASS '+name)};
  const closeDetail=async()=>{await page.keyboard.press('Escape'); await page.getByTestId('detail-dialog').waitFor({state:'hidden'})};
  const copied=()=>page.evaluate(()=>navigator.clipboard.readText());
  await check('离线单文件显示六项真实共享能力，不请求外部资源',async()=>{
    const standalone=path.join(output,'standalone.html'); fs.copyFileSync(html,standalone); await go(standalone);
    assert.equal(await rows().count(),6); assert.deepEqual(network,[]);
    await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true}); await page.screenshot({path:path.join(output,'preview.png')});
  });
  await check('首页显示五类能力和团队/示例来源切换',async()=>{
    await go(html); assert.equal(await page.locator('[data-testid="overview-grid"] .category-button').count(),6);
    assert.ok((await page.locator('#collection-note').innerText()).includes('示例'));
    await page.locator('[data-testid="overview-grid"] .category-button').filter({hasText:'Skill'}).click(); assert.equal(await rows().count(),1);
    await page.locator('#reset-filters').click(); assert.equal(await rows().count(),6);
  });
  await check('中文别名与多词搜索定位实际版本',async()=>{
    for(const [query,id] of [['审策划案','owner/design-review'],['整理会议','owner/meeting-summary'],['查漏项','owner/review-checklist'],['策划案 审查','owner/design-review']]){
      await page.getByTestId('search').fill(query); assert.equal(await rows().count(),1); assert.equal(await rows().first().getAttribute('data-id'),id);
    }
  });
  await check('中文输入法组合中不提前变更结果',async()=>{
    const input=page.getByTestId('search'); await input.fill('查漏项');
    await input.dispatchEvent('compositionstart');
    await input.evaluate(el=>{el.value='活动配置检查';el.dispatchEvent(new InputEvent('input',{bubbles:true,isComposing:true}))});
    assert.equal(await rows().count(),1); await input.dispatchEvent('compositionend'); assert.equal(await rows().count(),0);
  });
  await check('无内容返回真实空结果',async()=>{
    await page.getByTestId('search').fill('活动配置检查'); assert.equal(await rows().count(),0); assert.ok(/没有匹配|还没有团队上传/.test(await page.getByTestId('results').innerText()));
  });
  await check('详情绑定准确版本与依赖，键盘关闭返回焦点',async()=>{
    await page.getByTestId('search').fill('审策划案'); await rows().first().getByTestId('view-detail').click();
    const detail=page.getByTestId('detail-dialog'); await detail.getByText(/^入口材料 ·/).click(); assert.ok((await detail.innerText()).includes('先阅读实际策划案'));
    assert.equal(await page.getByTestId('version-select').inputValue(),'0.1.0');
    const detailText=await detail.innerText(); assert.ok(detailText.includes('作者')); assert.ok(detailText.includes('来源'));
    assert.equal(await detail.getByTestId('dependency-link').count(),1);
    await closeDetail(); assert.equal(await page.evaluate(()=>document.activeElement.tagName),'BUTTON');
  });
  await check('真实剪贴板成功后才显示复制反馈，目标包含版本和检查规则',async()=>{
    await rows().first().getByTestId('view-detail').click(); await page.getByTestId('reuse-action').click();
    await page.locator('#detail-action-note').filter({hasText:'已复制'}).waitFor();
    assert.ok((await page.locator('#detail-action-note').innerText()).includes('已复制')); await page.screenshot({path:path.join(output,'copy-success.png')}); const text=await copied(); assert.ok(text.includes('owner/design-review')); assert.ok(text.includes('0.1.0')); assert.ok(text.includes('check-reuse'));
    await closeDetail();
  });
  await check('拒绝剪贴板时可选择全文手动复制，不虚报完成',async()=>{
    await page.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>Promise.reject(new Error('synthetic denial'))}})});
    await rows().first().getByTestId('view-detail').click(); await page.getByTestId('reuse-action').click();
    await page.getByTestId('copy-dialog').waitFor(); assert.ok((await page.getByTestId('copy-text').inputValue()).includes('owner/design-review'));
    await page.getByTestId('copy-select').click();
    const selection=await page.getByTestId('copy-text').evaluate(el=>({start:el.selectionStart,end:el.selectionEnd,length:el.value.length}));
    assert.deepEqual(selection,{start:0,end:selection.length,length:selection.length});
    await page.keyboard.press('Escape'); await closeDetail();
  });
  await check('手机布局可读、无横向溢出，详情与主动作可达',async()=>{
    await go(html); await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(output,'mobile.png')}); await rows().last().scrollIntoViewIfNeeded(); const last=await rows().last().boundingBox(); assert.ok(last.y<844&&last.y+last.height>0); await page.screenshot({path:path.join(output,'mobile-bottom.png')}); await rows().first().scrollIntoViewIfNeeded();
    await rows().first().getByTestId('view-detail').click(); assert.ok(await page.getByTestId('reuse-action').isVisible());
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(output,'mobile-detail.png')}); await closeDetail(); await page.setViewportSize({width:1440,height:1000});
  });
  await check('历史正文命中打开历史准确版本，HTML/script仅为文字',async()=>{
    await go(path.join(fixtures,'versions.html')); await page.getByTestId('history-toggle').check();
    await page.getByTestId('search').fill('旧版专属词'); assert.equal(await rows().count(),1); await rows().first().getByTestId('view-detail').click();
    assert.equal(await page.getByTestId('version-select').inputValue(),'1.0.0');
    assert.ok((await page.getByTestId('detail-dialog').innerText()).includes('<img src='));
    assert.equal(await page.evaluate(()=>window.webInjected),undefined); assert.deepEqual(network,[]); await closeDetail();
  });
  await check('撤回、作废、依赖停用不生成普通使用指令',async()=>{
    for(const name of ['撤回测试能力','作废测试能力','依赖停用测试能力']){
      await page.getByTestId('search').fill(name); await rows().first().getByTestId('view-detail').click();
      if(!await page.getByTestId('version-select').inputValue())await page.getByTestId('version-select').selectOption('1.0.0'); assert.ok((await page.getByTestId('reuse-action').innerText()).includes('安全')); await closeDetail();
    }
  });
  await check('验证范围与通过失败记录同时可见',async()=>{
    await page.getByTestId('search').fill('多版本测试能力'); await rows().first().getByTestId('view-detail').click();
    await page.getByTestId('version-select').selectOption('2.0.0'); const text=await page.getByTestId('detail-dialog').innerText();
    assert.ok(text.includes('合成样例中的审查')); assert.ok(text.includes('合成通过记录')); assert.ok(text.includes('合成失败记录')); await closeDetail();
  });
  await check('改编关系展示精确来源而非只有一句摘要',async()=>{
    await page.getByTestId('search').fill('多版本测试能力'); await rows().first().getByTestId('view-detail').click();
    await page.getByText('查看精确改编来源',{exact:true}).click(); const text=await page.getByTestId('detail-dialog').innerText(); assert.ok(text.includes('bob/original')); assert.ok(text.includes('3.0.0')); assert.ok(text.includes('d'.repeat(64))); assert.ok(text.includes('c'.repeat(40))); await closeDetail();
  });
  await check('没有推荐不默认选择最新版，明确选择后才可使用',async()=>{
    await go(path.join(fixtures,'no-recommendation.html')); await page.getByTestId('search').fill('多版本测试能力');
    await rows().first().getByTestId('view-detail').click(); assert.equal(await page.getByTestId('version-select').inputValue(),''); assert.equal(await page.getByTestId('reuse-action').isEnabled(),false);
    await page.getByTestId('version-select').selectOption('1.0.0'); assert.equal(await page.getByTestId('reuse-action').isEnabled(),true); await closeDetail();
  });
  await check('验证筛选中的历史版仍保留真实推荐关系',async()=>{
    await go(path.join(fixtures,'versions.html')); await page.getByTestId('verification-filter').selectOption('unverified');
    const row=rows().filter({hasText:'多版本测试能力'}); const text=await row.innerText(); assert.ok(!text.includes('尚无推荐版本')); assert.ok(text.includes('2.0.0')); assert.ok(text.includes('1.0.0'));
    await row.getByTestId('view-detail').click(); assert.equal(await page.getByTestId('version-select').inputValue(),'1.0.0'); await closeDetail();
  });
  await check('处理中与维护请求单列，不计入已共享能力',async()=>{
    await go(path.join(fixtures,'versions.html')); const count=await rows().count(); await page.getByTestId('pending-nav').click();
    const text=await page.locator('#pending-list').innerText(); assert.ok(text.includes('能力投稿')); assert.ok(text.includes('指南维护')); assert.ok(text.includes('bob/pending'));
    await page.getByTestId('find-nav').click(); assert.equal(await rows().count(),count);
    await go(path.join(fixtures,'pending-unavailable.html')); await page.getByTestId('pending-nav').click(); assert.ok((await page.locator('#pending-list').innerText()).includes('不代表没有'));
  });
  await check('沉淀三入口与首次接入、更新指令遵循真实操作边界',async()=>{
    await go(html); await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>Promise.reject(new Error('synthetic denial'))}}));
    await page.getByTestId('contribute-nav').click();
    for(const [testid,required] of [['task-codex',['CODEX_HOME','不上传','元数据','中文草稿']],['task-organize',['不上传','保留原件']],['task-share',['自动检查','中文','不直接推共享分支','自动合并']]]){
      await page.getByTestId(testid).click(); await page.getByTestId('copy-dialog').waitFor(); const text=await page.getByTestId('copy-text').inputValue(); for(const term of required)assert.ok(text.includes(term),term); await page.keyboard.press('Escape');
    }
    await page.getByTestId('help-nav').click(); await page.locator('#setup-button').click(); await page.getByTestId('copy-dialog').waitFor(); assert.ok((await page.getByTestId('copy-text').inputValue()).includes('doctor')); await page.keyboard.press('Escape');
    await page.locator('#update-button').click(); await page.getByTestId('copy-dialog').waitFor(); const text=await page.getByTestId('copy-text').inputValue(); assert.ok(text.includes('刷新不等于同步 Git')); assert.ok(text.includes('保留最后一份完整 HTML')); await page.keyboard.press('Escape');
  });
  await check('剪贴板一直无回应也会进入人工复制，不留下旧成功提示',async()=>{
    await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>new Promise(()=>{})}}));
    await page.locator('#update-button').click(); await page.getByTestId('copy-dialog').waitFor({timeout:5000}); assert.equal(await page.getByTestId('toast').isVisible(),false); await page.keyboard.press('Escape');
  });
  await check('真实依赖跳转与业务输入不写入地址或本地存储',async()=>{
    await go(html); await page.getByTestId('search').fill('审策划案'); await rows().first().getByTestId('view-detail').click();
    await page.locator('#reuse-task').fill('合成业务原文不持久化'); assert.ok(!page.url().includes('合成业务')); assert.equal(await page.evaluate(()=>localStorage.length),0);
    await page.getByTestId('dependency-link').click(); assert.ok((await page.locator('#detail-title').innerText()).includes('检查清单')); assert.ok(page.url().includes('review-checklist')); await closeDetail();
  });
  await check('无能力数据能正常浏览和交接任务',async()=>{
    await go(path.join(fixtures,'empty.html')); assert.equal(await rows().count(),0); assert.ok(/没有匹配|还没有团队上传/.test(await page.getByTestId('results').innerText()));
  });
  assert.deepEqual(errors,[]); assert.deepEqual(network,[]);
  const report={browser:await browser.version(),checks,passed:checks.length,page_errors:errors,network_requests:network,source_html:path.basename(html)};
  fs.writeFileSync(path.join(output,'browser-report.json'),JSON.stringify(report,null,2));
  await browser.close(); console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exit(1)});
