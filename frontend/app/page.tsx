import Image from "next/image";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ImageUp,
  LineChart,
  MessageCircle,
  ShieldCheck,
  Smartphone,
  Users,
} from "lucide-react";

const steps = [
  {
    icon: ImageUp,
    title: "画像を送る",
    text: "SMSやメールのスクリーンショットをLINE公式アカウントへ送信します。",
  },
  {
    icon: ShieldCheck,
    title: "AIが確認",
    text: "本文、送信元、URL誘導などの危険な特徴を画像から読み取ります。",
  },
  {
    icon: MessageCircle,
    title: "短く返信",
    text: "危険度、理由、次に取る行動を高齢者にも分かりやすい文章で返します。",
  },
];

const levels = [
  {
    label: "安全レベル: 高",
    tone: "low",
    title: "危険な特徴は限定的",
    text: "公式アプリや公式窓口で確認すればよい状態を、過度に不安にさせず案内します。",
  },
  {
    label: "安全レベル: 中",
    tone: "medium",
    title: "少し注意が必要",
    text: "判断材料が足りない場合も、リンクや添付を開かず確認する行動へ誘導します。",
  },
  {
    label: "安全レベル: 低",
    tone: "high",
    title: "危険な可能性",
    text: "個人情報や支払い情報を入力しないよう、家族や公式窓口への相談を促します。",
  },
];

const features = [
  "スクリーンショット画像をそのまま相談",
  "危険度を3段階で表示",
  "理由と対応方法を最大3つに整理",
  "LINEで迷わず相談できる設計",
];

const protections = [
  {
    title: "Gmailの保護",
    items: [
      "迷惑メール・フィッシング・なりすまし判定",
      "危険URLや危険な添付ファイルの検知",
      "怪しいメールの迷惑メールフォルダ移動",
    ],
  },
  {
    title: "Outlookの保護",
    items: [
      "迷惑メールフォルダ振り分け",
      "フィッシング警告と危険URL検知",
      "危険な添付ファイルへの警告",
    ],
  },
  {
    title: "セキュリティソフトの保護",
    items: [
      "危険なサイトへのアクセス時の警告",
      "フィッシングサイトや偽ショッピングサイト検知",
      "偽銀行サイトへのアクセス時のブロック",
    ],
  },
];

const impersonatedCategories = [
  "通販サイト",
  "銀行",
  "決済サービス",
  "スマホ会社",
  "宅配業者",
  "公共料金",
];

const lineFriendUrl = "https://lin.ee/8ILjiWc";

export default function Home() {
  return (
    <main>
      <section className="hero" id="top">
        <header className="nav" aria-label="サイトナビゲーション">
          <a className="brand" href="#top" aria-label="詐欺チェッカー ホーム">
            <Image
              className="brandLogo"
              src="/logo-mark.svg"
              alt=""
              width={30}
              height={30}
              aria-hidden="true"
            />
            <span>詐欺チェッカー</span>
          </a>
          <nav>
            <a href="#purpose">目的</a>
            <a href="#flow">使い方</a>
            <a href="#levels">判定</a>
            <a href="#contact">導入相談</a>
          </nav>
        </header>

        <Image
          className="heroImage"
          src="/hero-phish-guard.png"
          alt="スマートフォンで詐欺SMSやメールをAIに相談する様子"
          fill
          priority
          sizes="100vw"
        />
        <div className="heroOverlay" />
        <div className="heroContent">
          <p className="eyebrow">LINEで詐欺SMS・メールをかんたん確認</p>
          <h1>詐欺チェッカー</h1>
          <p className="lead">
            怪しいSMSやメールのスクリーンショットを送るだけ。AIが危険度と対応方法を、短く分かりやすい日本語で返信します。
          </p>
          <div className="heroActions">
            <a
              className="primaryButton"
              href={lineFriendUrl}
              target="_blank"
              rel="noreferrer"
            >
              <MessageCircle size={20} aria-hidden="true" />
              友達追加する
            </a>
            <a className="secondaryButton" href="#flow">
              使い方を見る
            </a>
          </div>
          <dl className="stats" aria-label="サービスの特徴">
            <div>
              <dt>3段階</dt>
              <dd>危険度判定</dd>
            </div>
            <div>
              <dt>最大3つ</dt>
              <dd>理由と対応</dd>
            </div>
            <div>
              <dt>LINE</dt>
              <dd>相談導線</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="trustBand" aria-label="主な用途">
        <div className="sectionInner trustGrid">
          <div>
            <Smartphone size={24} aria-hidden="true" />
            <span>高齢者の家族サポート</span>
          </div>
          <div>
            <Users size={24} aria-hidden="true" />
            <span>自治体・地域窓口</span>
          </div>
          <div>
            <Clock3 size={24} aria-hidden="true" />
            <span>日常の不安をすぐ確認</span>
          </div>
          <div>
            <LineChart size={24} aria-hidden="true" />
            <span>家族や窓口で見守り</span>
          </div>
        </div>
      </section>

      <section className="section purposeSection" id="purpose">
        <div className="sectionInner">
          <div className="sectionHeader">
            <p className="eyebrow">Purpose</p>
            <h2>メールの警告だけでは、防ぎきれない不安に備える</h2>
            <p>
              GmailやOutlook、セキュリティソフトは強力な保護を行っています。それでも、受信トレイに届いた本物っぽいメールを人が信じてしまう場面が残ります。
            </p>
          </div>

          <div className="protectionGrid">
            {protections.map((protection) => (
              <article className="protectionCard" key={protection.title}>
                <div className="protectionIcon">
                  <ShieldCheck size={24} aria-hidden="true" />
                </div>
                <h3>{protection.title}</h3>
                <ul>
                  {protection.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>

          <div className="reasonPanel">
            <div>
              <p className="eyebrow">Why it still happens</p>
              <h3>どんな判定も100%ではありません</h3>
              <p>
                被害の多くは、迷惑メールフォルダに入らなかったメールではなく、受信トレイに届いた本物に見えるメールを信じてしまうケースです。正規メールと偽メールの差が小さく、警告が出ないこともあります。
              </p>
            </div>
            <div className="brandCloud" aria-label="なりすましに使われやすいカテゴリ例">
              {impersonatedCategories.map((category) => (
                <span key={category}>{category}</span>
              ))}
            </div>
          </div>

          <div className="purposeNote">
            <AlertTriangle size={22} aria-hidden="true" />
            <p>
              詐欺チェッカーは、既存のメール保護を置き換えるものではありません。警告が出なかったメールでも、少しでも迷ったときにスクリーンショットをLINEで相談できる、最後の確認窓口として利用します。
            </p>
          </div>
        </div>
      </section>

      <section className="section" id="flow">
        <div className="sectionInner">
          <div className="sectionHeader">
            <p className="eyebrow">Flow</p>
            <h2>迷った瞬間に、いつものLINEで相談</h2>
            <p>
              新しいアプリの操作を覚える必要はありません。受け取った画面を撮って送るだけで、次に取る行動まで届きます。
            </p>
          </div>
          <div className="stepGrid">
            {steps.map((step, index) => {
              const Icon = step.icon;
              return (
                <article className="stepCard" key={step.title}>
                  <div className="stepTop">
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <Icon size={26} aria-hidden="true" />
                  </div>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="section levelsSection" id="levels">
        <div className="sectionInner split">
          <div className="sectionHeader alignLeft">
            <p className="eyebrow">Risk Level</p>
            <h2>怖がらせず、でも見逃さない判定設計</h2>
            <p>
              結果は安全レベルとして返します。断定しすぎず、URLを開かない、公式窓口で確認する、家族へ相談する行動につなげます。
            </p>
            <ul className="featureList">
              {features.map((feature) => (
                <li key={feature}>
                  <CheckCircle2 size={18} aria-hidden="true" />
                  {feature}
                </li>
              ))}
            </ul>
          </div>
          <div className="levelStack">
            {levels.map((level) => (
              <article className={`levelCard ${level.tone}`} key={level.label}>
                <span>{level.label}</span>
                <h3>{level.title}</h3>
                <p>{level.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="contact">
        <div className="sectionInner cta">
          <AlertTriangle size={30} aria-hidden="true" />
          <h2>フィッシング相談を、LINEの窓口に</h2>
          <p>
            地域や家族向けの相談導線として、短い返信で不安を行動に変えます。怪しいと感じたら、まずはLINEで気軽に確認できます。
          </p>
          <a
            className="primaryButton dark"
            href={lineFriendUrl}
            target="_blank"
            rel="noreferrer"
          >
            <MessageCircle size={20} aria-hidden="true" />
            相談する
          </a>
        </div>
      </section>
    </main>
  );
}
