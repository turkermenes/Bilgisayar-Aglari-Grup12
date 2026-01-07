# QoS Odaklı Çok Amaçlı Rotalama Uygulaması (Grup 12)

Bu proje, **BSM307 - Bilgisayar Ağları** dersi kapsamında, karmaşık ağ topolojileri üzerinde servis kalitesi (QoS) gereksinimlerini optimize etmek amacıyla geliştirilmiştir. Uygulama, 250 düğümlü bir ağ üzerinde gecikme, güvenilirlik ve kaynak verimliliği gibi birbiriyle çelişen hedefleri aynı anda optimize eden bir rota bulucu sunar.

## 🚀 Proje Hakkında ve Teknik Detaylar

Modern veri merkezleri ve bulut ağları için tasarlanan bu uygulama, ağ üzerindeki darboğazları önlemek ve en güvenli, en hızlı yolu belirlemek için geliştirilmiştir. Rota seçimi yapılırken sadece mesafe değil, aşağıdaki kritik QoS metrikleri dikkate alınır:

1.  **Toplam Gecikme:** Yol üzerindeki tüm bağlantı gecikmeleri ile düğümlerdeki işlem (processing) sürelerinin toplamıdır.
2.  **Maksimum Güvenilirlik:** Düğümlerin ve hatların çalışma olasılıkları çarpılarak hesaplanır. Algoritmaların verimli çalışması için bu değer matematiksel olarak bir maliyet fonksiyonuna dönüştürülmüştür.
3.  **Kaynak Kullanımı:** Bağlantıların bant genişliği kapasitelerine göre belirlenen bir maliyet fonksiyonudur. Yüksek kapasiteli yolların tercih edilmesi sağlanır.

Sistem; React tabanlı modern bir arayüz, Electron ile masaüstü uygulama katmanı ve Python tabanlı güçlü bir matematiksel çözücü (solver) mimarisine sahiptir.

## 🧠 Kullanılan Algoritmalar

Proje, NP-Zor sınıfındaki bu problemi çözmek için iki ana meta-sezgisel algoritma sunar:

### 1. Karınca Kolonisi Optimizasyonu (ACO)
Bu algoritma, karıncaların yiyecek ararken en kısa yolu bulmalarını sağlayan feromon izlerini taklit eder.
* **İşleyiş:** Sanal karıncalar kaynaktan hedefe rastgele yollar keşfeder ve buldukları yolların kalitesine göre feromon bırakırlar.
* **Sezgisel Seçim:** Bir sonraki düğüm seçilirken hem mevcut feromon yoğunluğu hem de yolun QoS kalitesi (gecikme, güvenilirlik vb.) birlikte değerlendirilir.
* **Kısıt Kontrolü:** Algoritma, kullanıcının talep ettiği bant genişliğini (Demand) sağlayamayan hatları otomatik olarak eler.

### 2. Genetik Algoritma (GA)
Doğal seçilim ve evrimsel süreçleri temel alan bir yaklaşımdır.
* **Popülasyon:** İlk nesil, bant genişliği kısıtına uyan geçerli rotalardan oluşturulur.
* **Çaprazlama ve Mutasyon:** Mevcut rotalar (ebeveynler) ortak düğümleri üzerinden birleştirilerek yeni rota alternatifleri üretilir. Mutasyon aşamasında ise rotadaki bazı düğümler rastgele değiştirilerek yerel en iyiye takılma önlenir.
* **Elitizm:** Her neslin en başarılı rotaları korunarak bir sonraki nesle doğrudan aktarılır, böylece çözüm kalitesi sürekli artar.

## 🛠️ Kurulum ve Çalıştırma Adımları

Uygulamayı sisteminizde çalıştırmak için aşağıdaki adımları izleyin:

1.  **Bağımlılıkların Yüklenmesi:**
    Önce Node.js paketlerini, ardından Python kütüphanelerini yükleyin.
    ```bash
    npm install
    cd python
    pip install -r requirements.txt
    cd ..
    ```

2.  **Arayüz Hazırlığı:**
    Electron ve React arasındaki iletişimi sağlayan preload script'ini bir kez oluşturun.
    ```bash
    npm run build:preload
    ```

3.  **Geliştirme Modunda Başlatma:**
    Aşağıdaki komutla uygulamayı başlatın:
    ```bash
    npm run dev
    ```

## ⚙️ Kullanım Kılavuzu

1.  **Veri Setini Yükleyin:** Arayüzdeki dosya seçici butonları kullanarak `node_data.csv`, `edge_data.csv` ve `demand_data.csv` dosyalarını sisteme tanıtın.
2.  **Ağı Görselleştirin:** "Load Graph" butonu ile 250 düğümlü devasa topolojiyi ekrana getirin.
3.  **Parametreleri Ayarlayın:** Kaynak (S) ve Hedef (D) düğümlerini girin. QoS ağırlıklarını ($W_{delay} + W_{reliability} + W_{resource} = 1$) ihtiyacınıza göre belirleyin.
4.  **Hesapla:** Algoritmayı seçip "Run" butonuna bastığınızda bulunan rota grafik üzerinde kalın bir çizgiyle vurgulanacak ve sonuç metrikleri panelde listelenecektir.

## 🧬 Seed (Tohum) ve Tekrarlanabilirlik Bilgisi

Bilimsel kıyaslamalar için deneylerin tekrarlanabilir olması esastır. Bu nedenle:
* **Sabit Topoloji:** Uygulama içerisinde kullanılan ağ yapısı rastgele oluşturulmuş olsa da, sonuçların herkes için aynı olması adına bu yapı `node_data.csv` ve `edge_data.csv` dosyalarına kaydedilmiştir. Bu dosyalar üzerinden çalıştırıldığında her seferinde aynı 250 düğümlü ağ yapısı kullanılır.
* **Deterministik Algoritmalar:** Algoritmalar rastgelelik içerse de, kullanılan veri setleri ve belirli parametre setleri ile aynı koşullar altında karşılaştırılabilir sonuçlar üretmektedir.

---
**Grup 12 | Bilgisayar Ağları Proje Ekibi**