# X5 RetailHero 포트폴리오 — GitHub 업로드 가이드 (Windows)

현재 GitHub 연결 계정: `HUN-2`. 대상 저장소: `X5-RetailHero-Uplift` (아직 미생성).

## A. 먼저 저장소 만들기

1. [GitHub 새 저장소](https://github.com/new)에 접속하여 로그인합니다.
2. **Owner: HUN-2**, **Repository name: X5-RetailHero-Uplift**를 입력합니다.
3. Description 예: `Customer behavior heterogeneity and uplift-based CRM targeting using X5 RetailHero data.`
4. **Private**로 먼저 만들고 검증 후 **Public**으로 전환하는 편이 안전합니다. 처음부터 Public으로 만들어도 되지만 파일 검수 후 공개를 권장합니다.
5. **Add a README file / Add .gitignore / Choose a license**는 모두 선택하지 않습니다. 패키지에 README와 .gitignore가 포함되어 있습니다. **Create repository** 클릭.

## B. 업로드 — GitHub 웹에서

1. 전달받은 `X5-RetailHero-Uplift_GitHub_Ready.zip`의 압축을 먼저 풉니다.
2. 압축해제 후 `X5-RetailHero-Uplift` 폴더 **안의 내용 전체** (`README.md`, `.gitignore`, `sql/`, `analysis/`, `tableau/` 등)를 업로드합니다. ZIP 파일 자체를 단일 파일로 업로드하면 파일을 GitHub에서 바로 열 수 없습니다.
3. 새 저장소의 `uploading an existing file` 버튼 또는 `Add file → Upload files`로 이동하여 파일/폴더들을 드래그합니다. 브라우저에서 하위 폴더 보존 여부를 업로드 미리보기로 확인합니다.
4. 특히 `sql/`, `analysis/`, `tableau/data/`, `tableau/workbook/`이 의도대로 들어가는지 확인합니다. `.gitignore`도 빠지지 않도록 확인합니다.
5. Commit message: `Add complete X5 uplift analysis portfolio` → `Commit changes` 클릭.
6. 업로드 후 README 첫 화면이 보이는지, 워크북 `.twbx`가 존재하는지, `07_analysis_model_data.csv`, `purchases.csv.gz`, `08_test_predictions_LOCAL_ONLY.csv` 같은 로컬 원자료가 **없**는지 확인합니다.

GitHub 웹 인터페이스가 폴더 업로드를 보존하지 않으면, GitHub Desktop에서 로컬 폴더를 추가해 게시하는 방식을 이용합니다. (압축 푼 폴더에서 GitHub Desktop: `File → Add Local Repository → create a repository here`, 이후 `Publish repository`.)

## C. 공개 전 마무리

- Tableau Desktop/Public에서 `tableau/workbook/Who_Should_We_Persuade_public.twbx`를 열어 4개 Story와 선택 비율 매개변수가 정상 표시되는지 최종 확인합니다.
- 필요할 경우 재연결용 CSV는 `tableau/data/`에 포함되어 있습니다.
- GitHub 웹의 `Settings → General → Danger Zone → Change repository visibility`에서 Private→Public으로 바꿉니다. 공개 전 전체 파일을 다시 확인합니다.
- 공개 주소: `https://github.com/HUN-2/X5-RetailHero-Uplift`

대화로 안내받으며 진행하려면 우선 **저장소 생성 후 해당 URL을 전달**하면 됩니다. 이후 게시·공개 점검을 이어갈 수 있습니다.
