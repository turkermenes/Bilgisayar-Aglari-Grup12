import random
import numpy as np

class GeneticAlgorithm:
    
    def __init__(self, network_topology):
        '''
        :param network_topology: Dosyadan okuma yaparak oluşturduğumuz ağ graf veri yapısında bu obje ile tutuldu.
        '''
        self.network_topology = network_topology
        self.G = network_topology.G
        self.set_configurations()

    def set_configurations(self, population_size=200, mutation_rate=0.2, generations=1000, elitism_percentage=0.05, tournament_size=3, max_stagnation=50):
        '''
        :param population_size: Bu parametre popülasyonumuzda kaç kromozom (rota) olacağını belirler. 
        :param mutation_rate: Bu parametre bir kromozomdaki ara düğümlerden her birisi için mutasyon gerçekleşme oranını ifade eder. 0.0 ile 1.0 arasında değer alır.
        :param generations: Bu parametre bir kaynak düğümden hedef düğüme en iyi yolu bulma arayışını kaç jenerasyon boyunca sürdürüleceğini belirler.
        :param elitisim_percentage: Bu parametre oluşturulan popülasyonun yüzde kaçlık en iyi bireylerinin korunup sonraki popülasyona ekleneceğini belirler.
        :param tournament_size: Bu parametre crossover öncesinde ebeveyn seçerken popülasyondan bu sayıda rastgele kromozom (rota) alınıp onlardan en iyi fitness değerine sahip olanın seçilmesidir.
        :param max_stagnation: Bu parametre bir kaynak düğümden hedef düğüme giderken sonraki jenerasyon daha iyi fitness değerine sahip değilse stagnation (durgunluk) sayacı artırılır. Bu sayıya erişince de verimlilik amacıyla yeni rota arayışı sonlandırılır. 
        '''

        self.POPULATION_SIZE = population_size
        self.MUTATION_RATE = mutation_rate
        self.GENERATIONS = generations
        self.ELITISM_PERCENTAGE = elitism_percentage
        self.TOURNAMENT_SIZE = tournament_size
        self.MAX_STAGNATION = max_stagnation

    # Bu metotta başlangıç popülasyonumuzu kaynak, hedef düğüm ve talep edilen bant genişliğine göre oluşturuyoruz. Popülasyon, kromozomlardan oluşur.
    # Her bir kromozom bulunan rastgele bir rotayı temsil etmektedir. 
    def initialise_population(self, pop_size, source_node_id: int, target_node_id: int, bandwidth: int):
        '''
        :param pop_size: Popülasyon büyüklüğünü ifade eder.
        :param source_node_id: Kaynak düğümün id'sini ifade eder.
        :param target_node_id: Hedef düğümün id'sini ifade eder.
        :param bandwidth: Talep edilen bant genişliğine uygun rotalar bulmak amacıyla bant genişliği değeri parametre olarak alındı. 
        '''
        population = []
        
        count = 0
        max_count = pop_size * 50

        while len(population) < pop_size and count < max_count:
            count += 1

            visited = {source_node_id}
            
            random_chromosome = [source_node_id]
            if len(self.G[source_node_id]) == 0:
                continue
            current_node = source_node_id
            
            min_bandwidth = np.inf

            while current_node != target_node_id:
                all_neighbors = list(self.G[current_node].keys())
                valid_neighbors = [n for n in all_neighbors if n not in visited]
                if not valid_neighbors:
                    random_chromosome = []
                    break
                next_node = random.choice(valid_neighbors)
                
                current_link_bw = self.G[current_node][next_node]['bandwidth']
                if current_link_bw < min_bandwidth:
                    min_bandwidth = current_link_bw
                
                random_chromosome.append(next_node)
                visited.add(next_node)
                current_node = next_node
                
                if len(random_chromosome) > len(self.G.nodes):
                    random_chromosome = []
                    break
            
            if len(random_chromosome) > 0 and random_chromosome[-1] == target_node_id:
                
                if min_bandwidth > bandwidth:
                    if random_chromosome not in population:
                        population.append(random_chromosome)
                
        return population

    # Bulduğumuz kromozomların (rota) fitness (uygunluk) değerlerini hesaplamak için kullanacağımız metot.
    # Fitness hesaplaması yaparken çok amaçlı çözüm ile 3 metriğimiz arasında ağırlıklı toplam yöntemi ile denge kurmak istendi. 
    def calculate_fitness(self, chromosome, weight_delay, weight_reliability, weight_resource):
        '''
        :param chromosome: Fitness değerini hesaplayacağımız kromozomu (rota) temsil eder. Liste yapısındadır.
        :param weight_delay: Kromozomun fitness değeri hesaplamasında uygulanacak ağırlıklı toplam yönteminde toplam gecikme değerinin ağırlık değerini belirtir.
        :param weight_reliability: Kromozomun fitness değeri hesaplamasında uygulanacak ağırlıklı toplam yönteminde güvenilirlik maliyeti değerinin ağırlık değerini belirtir.
        :param weight_resource: Kromozomun fitness değeri hesaplamasında uygulanacak ağırlıklı toplam yönteminde ağ kaynak kullanımı değerinin ağırlık değerini belirtir.
        '''
        total_delay = total_reliability = resource_cost = fitness = 0
        
        # Total Delay (Toplam Gecikme) Hesaplaması - Minimizasyon
        # Yoldaki tüm bağlantı gecikmelerinin toplamı + ara düğümlerdeki (kaynak S ve hedef D hariç) tüm işlem gecikmelerinin toplamı

        total_link_delay = 0
        total_processing_delay = 0
        for i in range(len(chromosome) - 1):
            j = i + 1
            total_link_delay += self.G[chromosome[i]][chromosome[j]]['delay']
        
        for i in range(len(chromosome)):
            if i != 0 and i != len(chromosome) - 1:
                total_processing_delay += self.G.nodes[chromosome[i]]['processing_delay']

        total_delay = total_link_delay + total_processing_delay

        # Reliability Cost (Güvenilirlik Maliyeti) Hesaplaması - Minimizasyon

        total_link_reliability = 0
        total_node_reliability = 0
        for i in range(len(chromosome) - 1):
            j = i + 1
            total_link_reliability += -(np.log(self.G[chromosome[i]][chromosome[j]]['reliability']))
        
        for i in range(len(chromosome)):
            total_node_reliability += -(np.log(self.G.nodes[chromosome[i]]['node_reliability']))

        total_reliability = total_link_reliability + total_node_reliability

        # Resource Cost (Ağ Kaynak Kullanımı) Hesaplaması - Minimizasyon
        # Her bağlantının maliyeti, maksimum olası bant genişliğine (1 Gbps) göre ters orantılıdır.

        for i in range(len(chromosome) - 1):
            j = i + 1
            resource_cost += 1000 / self.G[chromosome[i]][chromosome[j]]['bandwidth']

        # Fitness (Uygunluk) Hesaplaması
        # Hesaplanan 3 metrik değeri ağırlıklı toplam ile dengelendi. Ağırlıklar toplamı 1'e eşit olmalıdır.

        fitness = weight_delay * total_delay + weight_reliability * total_reliability + weight_resource * resource_cost

        return float(fitness)
    
    # Ebeveyn seçimi yaparken turnuva seçimi yapmak için yazılan metot.
    # Turnuva seçiminde popülasyondan turnuva büyüklüğü sayısınca rastgele bireyler seçilerek fitness değerleri karşılaştırılır ve en iyi fitness değerine sahip olan birey ebeveyn olur.
    def tournament_selection(self, population, tournament_size, weights):
        '''
        :param population: Turnuva seçimi yapmak istediğimiz popülasyonu ifade eder.
        :param tournament_size: Turnuva büyüklüğünü temsil eder. Parametre olarak aldığımız popülasyon içerisinden kaç tane rastgele birey seçeceğimizi ifade eder. 
        :param weights: Fitness değerlerini hangi ağırlıklar üzerinden hesaplayacağımızı belirlemek amacıyla ağırlıklar parametre olarak alındı.
        '''
        selected_parents = []
        for _ in range(2):
            # Popülasyondan turnuva büyüklüğü sayısınca rastgele birey seçilir. 
            tournament = random.sample(population, min(len(population), tournament_size))
            best_fitness = np.inf
            best_parent = None
            for p in tournament:   
                fitness = self.calculate_fitness(p, weights['delay'], weights['reliability'], weights['resource'])
                if fitness < best_fitness:
                    best_fitness = fitness
                    best_parent = p
            # En iyi fitness değerine sahip olan bireyler ebeveyn olarak belirlenir. 
            selected_parents.append(best_parent)

        return selected_parents
    
    def crossover(self, parent1, parent2):
        '''
        :param parent1: Çaprazlama yapacağımız ilk ebeveyni, kromozomu (rota) temsil eder.
        :param parent2: Çaprazlama yapacağımız ikinci ebeveyni, kromozomu (rota) temsil eder.
        
        Popülasyonda çeşitliliği artırıp daha iyi rotalar bulmak amacıyla crossover (çaprazlama) yapılmaktadır.
        Yazılan crossover metoduna parametre olarak verilen 2 ebeveynin eğer ara düğümlerinde ortak bir düğümü varsa o düğümün bulunduğu indeks her iki ebeveynde de çaprazlama noktası olarak belirlenir.
        Daha sonra belirlenen noktalar üzerinden çaprazlama gerçekleştirilerek 2 yeni birey elde edilir. Eğer iki ebeveyn ortak düğüme sahip değilse metot ebeveynleri değiştirmeden döndürür.
        '''
        route1 = parent1
        route2 = parent2

        if min(len(route1), len(route2)) > 2 and route1 != route2:
            shorter = route1 if len(route1) < len(route2) else route2
            longer = route2 if len(route2) > len(route1) else route1
            crossover_point_short = 0
            crossover_point_long = 0

            for i in range(len(shorter) - 1):
                if i != 0:
                    if shorter[i] in longer and longer[0] != shorter[i] and longer[len(longer) - 1] != shorter[i]:
                        # İki ebeveynde de ortak düğüm varsa bu düğümün iki ebeveyndeki indekslerini tutuyoruz. 
                        crossover_point_short = i
                        crossover_point_long = longer.index(shorter[i])
                        break
            
            if crossover_point_short != 0 and crossover_point_long != 0:
                # Belirlenen çaprazlama noktalarından parça değişimi gerçekleştiriliyor. 
                offspring1_route = shorter[:crossover_point_short] + longer[crossover_point_long:]
                offspring2_route = longer[:crossover_point_long] + shorter[crossover_point_short:]
            else:
                offspring1_route = route1
                offspring2_route = route2

            return offspring1_route, offspring2_route
        else:
            return parent1, parent2
        

    def mutation(self, chromosome, mutation_rate):
        '''
        :param chromosome: Mutasyon gerçekleştirilecek kromozom (rota) ifade eder. 
        :param mutation_rate: Kromozomun düğümlerden her birinde mutasyonun gerçekleşme oranını ifade etmektedir. 0.0 ile 1.0 arasında değer alır.

        Mutasyon gerçekleştirilirken kromozomun her bir düğümünde adım adım döngüyle dolaşılır eğer ilk veya son düğüm değilse hesaplanan rastgele değer mutasyon oranından daha küçükse
        o düğümün önceki ve sonraki düğümlerinin ortak komşuları arasından mevcut düğümün dışında başka bir düğüm seçilerek bağlantı koparılmadan mutasyon gerçekleştirilmiş olunur.
        '''
        mutation_rate = min(1, mutation_rate)
        mutated_chromosome = list(chromosome)
        first_gene = mutated_chromosome[0]
        last_gene = mutated_chromosome[-1]
        for gene in mutated_chromosome: 
            if gene != first_gene and gene != last_gene:
                i = mutated_chromosome.index(gene)
                r = random.random()
                if r <= mutation_rate:
                    prev = mutated_chromosome[i - 1]
                    next = mutated_chromosome[i + 1]

                    prev_adj = set(self.G.adj[prev].keys())
                    next_adj = set(self.G.adj[next].keys())

                    if prev in next_adj:
                        mutated_chromosome.remove(gene)
                        
                    else:
                        intersect_adj = prev_adj.intersection(next_adj)

                        kesisim = list(intersect_adj)
                        if gene in kesisim:
                            kesisim.remove(gene)

                        if len(kesisim) > 0:
                            new_node = random.choice(kesisim) 
                            mutated_chromosome[i] = new_node      
                        else:
                            continue    
                    
        return mutated_chromosome
    
    # Popülasyonumuzu sıralamak için quick sort algoritmasını kullandık. 
    def quick_sort(self, population, w_d, w_r, w_res):
        '''
        :param population: Sıralayacağımız popülasyonu temsil eder.
        :param w_d: Toplam gecikme (Total delay) metriğinin ağırlık katsayısını ifade eder.
        :param w_r: Güvenilirlik maliyeti (Reliability cost) metriğinin ağırlık katsayısını ifade eder.
        :param w_res: Ağ kaynak kullanımı (Resource cost) metriğinin ağırlık katsayısını ifade eder.
        '''
        if len(population) <= 1:
            return population
        pivot = population[len(population) // 2]
        pivot_fitness = self.calculate_fitness(pivot, w_d, w_r, w_res)

        left = []    
        middle = []  
        right = []

        for chrom in population:
            fitness = self.calculate_fitness(chrom, w_d, w_r, w_res)
            
            if fitness < pivot_fitness:
                left.append(chrom)
            elif fitness > pivot_fitness:
                right.append(chrom)
            else:
                middle.append(chrom)

        return (self.quick_sort(left, w_d, w_r, w_res) + 
                middle + 
                self.quick_sort(right, w_d, w_r, w_res))        
   
    # Popülasyonumuzu sıralayarak en iyi bireylerin en başa gelmesini sağlıyoruz. Ardından en iyi bireyleri elitizm ile saklayarak sonraki nesillere değişmeden geçmesini sağlıyoruz.
    def sort_population(self, population, weights):
        '''
        :param population: Sıralama yapacağımız popülasyonu temsil eder.
        :param weights: Popülasyonu sıralarken her bireyin fitness değerine göre sıralama yapılacağından hangi ağırlık kattsayılarına göre yapılacağını tutan değer. 
        '''
        return self.quick_sort(population, weights['delay'], weights['reliability'], weights['resource'])

    # Algoritmamızın optimizasyonda kullanacağımız ana metodu.
    def genetic_algorithm(self, source_node_id: int, target_node_id: int, demand_bandwidth: int, weights=None):
        '''        
        :param source_node_id: Kaynak düğümün id değerini tutar.
        :param target_node_id: Hedef düğümün id değerini tutar.
        :param demand_bandwidth: Talep edilen bant genişliğini tutar. 
        :param weights: Hangi ağırlık katsayılarına göre fitness değerlerinin hesaplanacağını tutar. 
        '''
        if weights is None:
            weights = {'delay': 0.33, 'reliability': 0.33, 'resource': 0.33}

        # Başlangıç popülasyonumuzu oluşturuyoruz.
        population = self.initialise_population(self.POPULATION_SIZE, source_node_id, target_node_id, demand_bandwidth)

        if not population:
            print(f"Uyarı: {source_node_id} -> {target_node_id} için başlangıç popülasyonu oluşturulamadı.")
            return None

        # Başlangıç popülasyonumuzu sıralayarak en iyi bireylerin en başa geçmesini sağlıyoruz.
        population = self.sort_population(population, weights)
        best_fitness = float('inf')

        # Duraksama sayacı tanımlandı.
        stagnation_counter = 0

        best_routes_per_generation = []


        for generation in range(self.GENERATIONS):
            new_population = []

            # Elitizm yaparak en iyi bireylerin yeni popülasyona değişmeden geçmesini sağlıyoruz.
            elite_chromosomes = population[:int(self.ELITISM_PERCENTAGE * self.POPULATION_SIZE)]
            new_population.extend(elite_chromosomes)

            # Genetik algoritmada popülasyon boyutu sabit olmalıdır. Bu nedenle yeni oluşturduğumuz popülasyonun boyutu belirlediğimiz sayıya ulaşana kadar crossover ve mutasyon yaparak popülasyonu dolduruyoruz.
            while len(new_population) < self.POPULATION_SIZE:
                # Turnuva seçimi yapılarak ebeveynler belirlendi.
                parent1, parent2 = self.tournament_selection(population, self.TOURNAMENT_SIZE, weights)

                # İlk 2 yeni birey ebeveynlerin crossover geçirmesi sonucunda oluşturuldu.
                offspring1, offspring2 = self.crossover(parent1, parent2)
                mutation_rate = self.MUTATION_RATE
            
                # Eğer crossover yapılamamışsa mutasyon oranı artırılarak çeşitliliğin sağlanması ve daha iyi bireyler bulunması amaçlandı.
                if offspring1 == parent1 and offspring2 == parent2:
                    mutation_rate = min(1, mutation_rate + 0.5)

                # 3. ve 4. yeni bireyler çaprazlama sonucu oluşan 1. ve 2. yeni bireylerin mutasyon geçirmesi sonucunda elde ediliyor. 
                offspring3 = self.mutation(offspring1, mutation_rate)
                offspring4 = self.mutation(offspring2, mutation_rate)

                offsprings = [offspring1, offspring2, offspring3, offspring4]

                # Yeni oluşturduğumuz bireylerden popülasyonda yer almayanlar popülasyona eklendi. 
                for offspring in offsprings:
                    if offspring not in new_population:
                        new_population.append(offspring)


            population = new_population
            population = self.sort_population(population, weights)

            best_chromosome = population[0]
            best_routes_per_generation.append(best_chromosome)

            # Mevcut popülasyonun en iyi kromozomumun fitness değeri hesaplandı.
            current_best_fitness = self.calculate_fitness(best_chromosome, weights['delay'], weights['reliability'], weights['resource'])
            if current_best_fitness < best_fitness:
                best_fitness = current_best_fitness
                print(f'{generation}. jenerasyon en iyi fitness: {best_fitness}')
                # Önceki jenerasyonlardan daha iyi bir fitness değeri bulunduğu için duraksama sayacı sıfırlandı.
                stagnation_counter = 0
            else:
                # Önceki jenerasyonlardan daha iyi olmayan bir fitness değeri bulunduğu için duraksama sayacı bir artırıldı.
                stagnation_counter += 1
                
            # Durgunluk sayacı belirlediğimiz maksimum durgunluk sayısına erişince program sonlandırılarak verimlilik amaçlanıyor. 
            if stagnation_counter >= self.MAX_STAGNATION:
                print(f"Durgunluk dolayısıyla {generation}. jenerasyonda sonlandırılıyor.")
                break

        if generation == self.GENERATIONS - 1:
            print(f"Maksimum jenerasyon sayısına ulaşıldığı için {generation}. jenerasyonda sonlandırılıyor.")

        print(f"Best fitness değeri: {best_fitness}")
        print(f"Bulunan en iyi rota: {best_chromosome}")

        return best_chromosome