const { chromium } = require('playwright');

(async () => {
  console.log("=== RAPTOR RE-HOTFIX E2E VERIFICATION START ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // 1. Navigate to App
    console.log("1. Navigating to http://localhost:3000...");
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });

    // 2. Test Invalid Login Credentials Korean Error
    console.log("2. Testing Invalid Login Credentials message...");
    const authButton = page.locator('button:has-text("Sign In / API Settings")');
    await authButton.click();
    await page.waitForTimeout(500);

    // Fill wrong credentials
    await page.fill('input[type="email"]', 'nonexistent_user@kie.ai');
    await page.fill('input[type="password"]', 'wrongPassword123!');
    const submitBtn = page.locator('button[type="submit"]');
    await submitBtn.click();
    
    // Wait for the red alert box to appear (max 10s)
    console.log("Waiting for error alert to appear...");
    const errorAlert = page.locator('div.text-red-400');
    await errorAlert.waitFor({ state: 'visible', timeout: 10000 });

    // Take screenshot of wrong credentials error
    await page.screenshot({ path: 'outputs/e2e_login_failed_error.png' });

    // Extract error text
    const errorText = await errorAlert.innerText();
    console.log("Login Error Message found in UI:", errorText);
    
    if (errorText && errorText.includes("이메일 또는 비밀번호가 올바르지 않습니다")) {
      console.log("SUCCESS: Invalid Login Korean alert check passed!");
    } else {
      console.error("FAIL: Invalid Login error warning not visible or incorrect translation!", errorText);
    }

    // 3. Register a New Account (Sign Up)
    console.log("3. Registering a new account...");
    const switchButton = page.locator('button:has-text("가입하기")');
    if (await switchButton.count() > 0) {
      await switchButton.click();
    }
    const testEmail = `recheck_user_${Date.now()}@kie.ai`;
    const testPassword = "securePassword123!";
    await page.fill('input[type="email"]', testEmail);
    await page.fill('input[type="password"]', testPassword);
    await submitBtn.click();
    
    // Wait for signup process and transition to logged in dashboard
    await page.waitForTimeout(3000);
    console.log("Signup complete.");

    // 3.5. Logout the auto-registered dummy session to perform real login
    console.log("3.5. Logging out dummy signup session...");
    const accountTab = page.locator('button:has-text("계정")');
    await accountTab.click();
    await page.waitForTimeout(500);
    const logoutBtn = page.locator('button:has-text("안전한 로그아웃")');
    await logoutBtn.click();
    await page.waitForTimeout(1000);

    // 3.6. Perform ACTUAL LOGIN to acquire real Supabase Session Token
    console.log("3.6. Performing real login to acquire token...");
    await authButton.click();
    await page.waitForTimeout(500);
    
    // If the modal is in Signup mode, switch to Login mode
    const loginSwitchBtn = page.locator('button:has-text("로그인하기")');
    if (await loginSwitchBtn.count() > 0) {
      console.log("Switching to Login Mode...");
      await loginSwitchBtn.click();
      await page.waitForTimeout(300);
    }
    
    // Clear and Fill Form
    const emailInput = page.locator('input[type="email"]');
    const passwordInput = page.locator('input[type="password"]');
    await emailInput.fill('');
    await emailInput.fill(testEmail);
    await passwordInput.fill('');
    await passwordInput.fill(testPassword);
    
    await submitBtn.click();
    
    // Wait for the Profile/Account button containing "@" to appear (means login success)
    console.log("Waiting for profile button indicating successful login...");
    const profileBtn = page.locator('button:has-text("@")');
    await profileBtn.waitFor({ state: 'attached', timeout: 10000 });
    console.log("Login success confirmed in UI!");
    
    const localStorageKeys = await page.evaluate(() => {
      return Object.keys(localStorage);
    });
    console.log("LocalStorage Keys after login:", localStorageKeys);

    const storeAfterLogin = await page.evaluate(() => {
      const data = localStorage.getItem('raptor-workflow-storage');
      return data ? JSON.parse(data) : null;
    });
    console.log("Logged in email saved in store:", storeAfterLogin?.state?.user?.email);
    
    // Capture user details to Node.js context for cross-reload restoration
    const currentUser = storeAfterLogin?.state?.user;
    const currentUserId = storeAfterLogin?.state?.userId;

    // 4. Inject Mock State for Step 3 to verify Layout and Render Headers (Keep Actual User Session!)
    console.log("4. Injecting Mock Step 3 workflow data into LocalStorage (preserving real session)...");
    await page.evaluate(({ user, userId }) => {
      const currentStorage = JSON.parse(localStorage.getItem('raptor-workflow-storage') || '{}');
      const stateObj = {
        state: {
          ...currentStorage.state,
          step: 3,
          inputMode: 'manual',
          productData: { name: 'Recheck Product', url: '', images: [], duration: 15, includeTag: false, targetLanguage: '한국어', purpose: '쇼핑 전환', targetAudience: '', tone: '리뷰형' },
          finalAssets: {
            strategy: { hook: "Test Hook Strategy" },
            upload_package: { titles: ["Title 1", "Title 2"], hashtags: ["tag1", "tag2"] },
            script: [
              { scene_number: 1, dialogue: "첫번째 씬 대사", visual_description: "첫번째 이미지 묘사", image_url: "https://api.kie.ai/outputs/e2e_test_image.png", status: "ready" }
            ]
          },
          kieKey: "kie-test-api-key-123456789",
          isKeyConfigured: true,
          aspectRatio: "1:1",
          user: user, // Keep valid auth user
          userId: userId // Keep valid auth userId
        },
        version: 0
      };
      localStorage.setItem('raptor-workflow-storage', JSON.stringify(stateObj));
    }, { user: currentUser, userId: currentUserId });

    // Reload page to apply injected store
    console.log("Reloading page to hydrate injected state...");
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(2500);

    // E2E Session Restore: 새로고침 후 Supabase Client 초기화 시 세션 유실되는 문제를 방지하기 위해 LocalStorage 재동기화
    console.log("Restoring session in localStorage to bypass headless reload auth drop...");
    await page.evaluate(({ user, userId }) => {
      const currentStorage = JSON.parse(localStorage.getItem('raptor-workflow-storage') || '{}');
      if (currentStorage.state) {
        currentStorage.state.user = user;
        currentStorage.state.userId = userId;
        localStorage.setItem('raptor-workflow-storage', JSON.stringify(currentStorage));
      }
    }, { user: currentUser, userId: currentUserId });

    // Reload once more to ensure restoration takes effect
    console.log("Final reload for session sync...");
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);

    const storeAfterReload = await page.evaluate(() => {
      const data = localStorage.getItem('raptor-workflow-storage');
      return data ? JSON.parse(data) : null;
    });
    console.log("User email after reload:", storeAfterReload?.state?.user?.email);
    console.log("UserId after reload:", storeAfterReload?.state?.userId);

    // Take screenshot of step 3 layout
    await page.screenshot({ path: 'outputs/e2e_step3_layout_injected.png' });

    // 5. Verify Step 4 Navigation Button Position (should be under Global Asset Pack)
    console.log("5. Verifying Step 4 Button position relative to Global Asset Pack...");
    const buttonPositionCheck = await page.evaluate(() => {
      const headings = Array.from(document.querySelectorAll('h3'));
      const assetPack = headings.find(h => h.textContent.includes("Global Asset Pack"));
      
      const buttons = Array.from(document.querySelectorAll('button'));
      const step4Btn = buttons.find(b => b.textContent.includes("Step 4") || b.textContent.includes("비디오 생성") || b.textContent.includes("비디오 생성/렌더링 단계로 이동"));
      
      if (!assetPack || !step4Btn) {
        return { error: "Elements not found", assetPackFound: !!assetPack, step4BtnFound: !!step4Btn };
      }

      const assetPackRect = assetPack.getBoundingClientRect();
      const btnRect = step4Btn.getBoundingClientRect();
      
      return {
        assetPackTop: assetPackRect.top,
        btnTop: btnRect.top,
        isBtnBelowAssetPack: btnRect.top > assetPackRect.top
      };
    });
    console.log("DOM Position Check Result:", buttonPositionCheck);
    if (buttonPositionCheck.isBtnBelowAssetPack) {
      console.log("SUCCESS: Step 4 button is correctly positioned under Global Asset Pack!");
    } else {
      console.error("FAIL: Step 4 button layout position is incorrect!", buttonPositionCheck);
    }

    // 6. Test Video Rendering API Key Headers Binding
    console.log("6. Clicking Step 4 Button & Testing Video Rendering request headers...");
    const step4Btn = page.locator('button:has-text("Step 4")');
    if (await step4Btn.count() > 0) {
      await step4Btn.click();
    } else {
      // Fallback selector for Korean text button
      const koBtn = page.locator('button:has-text("비디오 생성/렌더링 단계로 이동")');
      await koBtn.click();
    }
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'outputs/e2e_step4_entered.png' });

    // Listen to network request
    let requestHeaders = null;
    let requestPayload = null;
    page.on('request', request => {
      if (request.url().includes('/api/render-stream')) {
        requestHeaders = request.headers();
        try {
          requestPayload = JSON.parse(request.postData());
        } catch (e) {}
      }
    });

    console.log("Clicking Render Video button...");
    const renderVideoBtn = page.locator('button:has-text("최종 비디오 렌더링 시작")');
    if (await renderVideoBtn.count() > 0) {
      await renderVideoBtn.click();
      await page.waitForTimeout(3000); // 3s wait to capture CSRF + streaming request trigger
    }
    
    console.log("Intercepted /api/render-stream headers:", requestHeaders);
    if (requestHeaders && requestHeaders['x-byok-kie'] === 'kie-test-api-key-123456789') {
      console.log("SUCCESS: X-BYOK-KIE header successfully bound with Zustand kieKey!");
    } else {
      console.error("FAIL: X-BYOK-KIE header is missing or has incorrect value!", requestHeaders);
    }

    console.log("Intercepted /api/render-stream payload:", requestPayload);
    if (requestPayload && requestPayload.aspect_ratio === '1:1') {
      console.log("SUCCESS: aspect_ratio successfully bound with Zustand aspectRatio (1:1)!");
    } else {
      console.error("FAIL: aspect_ratio is missing or has incorrect value in payload!", requestPayload);
    }

    // 7. Test Logout / Account Switch workflow reset (Sterilization)
    console.log("7. Logging out and logging in as a different user to verify state reset...");
    
    const modalVisible = await page.locator('text=RAPTOR 통합 대시보드').count() > 0;
    if (!modalVisible) {
      const profileBtn = page.locator('button:has-text("@")');
      await profileBtn.click();
      await page.waitForTimeout(500);
    }
    const accountTab2 = page.locator('button:has-text("계정")');
    await accountTab2.click();
    await page.waitForTimeout(500);
    
    await logoutBtn.click();
    await page.waitForTimeout(1000);
    console.log("Logged out successfully.");

    const testEmail2 = `different_user_${Date.now()}@kie.ai`;
    console.log(`Signing up as a different user: ${testEmail2}...`);
    await authButton.click();
    await page.waitForTimeout(500);
    const signUpTab = page.locator('button:has-text("가입하기")');
    if (signUpTab && await signUpTab.count() > 0) {
      await signUpTab.click();
    }
    await page.fill('input[type="email"]', testEmail2);
    await page.fill('input[type="password"]', testPassword);
    await submitBtn.click();
    await page.waitForTimeout(2000);

    const storeAfterSwitch = await page.evaluate(() => {
      const data = localStorage.getItem('raptor-workflow-storage');
      return data ? JSON.parse(data) : null;
    });
    console.log("Current Step after account switch:", storeAfterSwitch?.state?.step);
    console.log("Current Product Name after account switch:", storeAfterSwitch?.state?.productData?.name);
    
    if (storeAfterSwitch?.state?.step === 0 && storeAfterSwitch?.state?.productData?.name === '') {
      console.log("SUCCESS: State fully reset (clean canvas Step 1) on account switch!");
    } else {
      console.error("FAIL: State was not reset after logging in as a different user!", storeAfterSwitch?.state);
    }

  } catch (err) {
    console.error("E2E Test Execution Error:", err);
  } finally {
    await browser.close();
    console.log("=== RAPTOR RE-HOTFIX E2E VERIFICATION END ===");
  }
})();
